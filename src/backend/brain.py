"""
Lithe — The Brain (F-01: Core LLM Connection + F-06: Candid Persona)

This module is the primary interface to the Gemini LLM. It:
  1. Creates a Gemini client using the secure API key from config.
  2. Detects the safeword to toggle between candid and compliant personas.
  3. Sends the user's message with the appropriate system prompt.
  4. Handles function calling (tools) and multi-turn execution within a single request.
  5. Falls back to a local Ollama model when Gemini is unreachable (Phase 2).
  6. Returns the model's text response.
"""

import httpx
import difflib
from google.genai import types, errors
from google import genai

from src.backend.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
)
from src.backend.prompts.system_prompt import (
    CANDID_SYSTEM_PROMPT,
    COMPLIANT_SYSTEM_PROMPT,
    detect_safeword,
)
from src.backend.retrieval import (
    get_file_context_blocks,
    read_file_securely,
    MAX_FILE_SIZE_BYTES,
)
from src.backend.context_budget import (
    MAX_HISTORY_MESSAGES,
    drop_orphan_prefix,
    trim_blocks,
    trim_history,
)
from src.backend.ollama_bridge import call_name_and_args, to_ollama_messages
from src.backend.tools import execute_rename, execute_delete, execute_write, execute_read
from src.backend.memory import search_files_by_name, record_action, insert_auto_summary
from src.backend.data_tools import profile_data as _profile_data, inline_chart as _inline_chart
from src.backend.watch_rules import (
    create_watch_rule as _create_watch_rule,
    list_watch_rules as _list_watch_rules,
    delete_watch_rule as _delete_watch_rule,
)
import os
import json
import time

# Global state for pausing execution during tool confirmation
_pending_session: list[types.Content] | None = None
_pending_tool_calls = None
_pending_config = None
_pending_tool_map = None
# Rounds already spent when a mutating tool paused the loop, so confirming it
# resumes with the remaining budget instead of ending the turn.
_pending_rounds_used = 0

_pending_ollama_messages = None
_pending_ollama_tool_calls = None
_pending_ollama_tool_map = None

# Global state for conversation history
_chat_history: list[types.Content] = []
_current_conversation_id: str | None = None

# Retrieved file content for the current conversation, deliberately kept OUT
# of _chat_history. F-04 used to append it to the user's message, which was
# then persisted and replayed on every later turn -- three named files meant
# ~300KB welded onto every request for the life of the conversation. Held here
# as (path, block) pairs instead, re-sent from a bounded cache each turn so a
# follow-up question still sees the file while the transcript stays small.
_context_blocks: list[tuple[str, str]] = []

# Global state for telemetry
last_token_counts = {"prompt": 0, "candidates": 0, "total": 0}
active_engine = "gemini"

# What the most recent Ollama turn produced, in the same module-global style as
# last_token_counts. _ollama_chat returns only text (or a proposal), so without
# this the caller cannot tell whether a tool ran -- which it must know for two
# reasons: the hallucination guard is only meaningful when none did, and a
# chart has to be handed to the UI rather than dropped.
last_ollama_turn = {"rounds": 0, "chart": None}

# Extra sampling options merged into every Ollama request. Empty in production,
# so the model's own defaults apply exactly as before. The capability
# evaluation sets a per-repeat `seed` here: an identical payload plus an
# identical seed gives identical output, which is what makes two runs of the
# suite comparable. Without it the score swung 86 -> 64 -> 86 on byte-identical
# requests, and sampling noise was indistinguishable from a regression.
OLLAMA_OPTIONS: dict = {}

from src.backend.logger import logger

# ---------------------------------------------------------------------------
# Gemini client (initialized once at module load)
# ---------------------------------------------------------------------------
try:
    _client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.exception(f"Fatal error during Gemini client initialization: {e}")
    _client = None

# --- Feature 4 (Tier 2): Persistent Chat History ---
import uuid
import json
from src.backend.memory import save_message, get_chat_history, get_latest_conversation_id, get_app_state, set_app_state

def _load_history():
    global _chat_history
    global _current_conversation_id
    global _context_blocks

    _chat_history.clear()
    # Retrieved file content is per-session and never persisted, so a reload
    # must start with none of it rather than the previous conversation's.
    _context_blocks = []

    # Prefer the explicit active-conversation pointer (set by new_conversation);
    # fall back to the latest message's conversation for pre-existing databases.
    _current_conversation_id = get_app_state("active_conversation_id") or get_latest_conversation_id()
    if not _current_conversation_id:
        _current_conversation_id = str(uuid.uuid4())
        set_app_state("active_conversation_id", _current_conversation_id)
        return

    rows = get_chat_history(_current_conversation_id)
    if len(rows) > MAX_HISTORY_MESSAGES:
        # A long transcript would be trimmed away at request time anyway, so
        # rebuilding Content objects for all of it is wasted startup work.
        rows = rows[-MAX_HISTORY_MESSAGES:]

    for row in rows:
        parts = []
        if row["content"]:
            parts.append(types.Part.from_text(text=row["content"]))
        if row["tool_proposal_json"]:
            for call_data in _as_list(json.loads(row["tool_proposal_json"])):
                parts.append(types.Part.from_function_call(
                    name=call_data["name"], args=call_data["args"]
                ))
        if row["tool_resolution"]:
            for res_data in _as_list(json.loads(row["tool_resolution"])):
                parts.append(types.Part.from_function_response(
                    name=res_data["name"], response=res_data["response"]
                ))
        
        if parts:
            _chat_history.append(types.Content(role=row["role"], parts=parts))

    # Slicing to the newest N rows can cut into a tool exchange, leaving a
    # function_response with no matching call -- which Gemini rejects outright.
    _chat_history[:] = drop_orphan_prefix(_chat_history)

def new_conversation() -> str:
    """Starts a new conversation by resetting the global state."""
    global _chat_history
    global _current_conversation_id
    global _context_blocks
    _chat_history.clear()
    _context_blocks = []
    _current_conversation_id = str(uuid.uuid4())
    set_app_state("active_conversation_id", _current_conversation_id)
    return _current_conversation_id

def switch_conversation(conversation_id: str) -> str:
    """Makes an existing conversation active and reloads it into LLM context.

    Writing the pointer first lets _load_history do the rest -- without the reload
    the model would keep answering from the previous chat's history.
    """
    set_app_state("active_conversation_id", conversation_id)
    _load_history()
    return _current_conversation_id

def _as_list(decoded):
    """Rows written before parallel calls were stored hold a bare object."""
    return decoded if isinstance(decoded, list) else [decoded]


def _save_content(content_obj: types.Content):
    """Persist one turn, keeping every function call and response it carries.

    A model may emit several function calls in one turn. This used to assign
    rather than accumulate, so only the last survived: a turn with two calls
    reloaded with one call and one response, which is not a valid payload.
    Stored as a JSON list now; _as_list keeps existing single-object rows
    readable.
    """
    try:
        content_text = ""
        calls = []
        resolutions = []
        for part in content_obj.parts:
            if part.text:
                content_text += part.text
            elif part.function_call:
                calls.append({
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args or {}),
                })
            elif part.function_response:
                resolutions.append({
                    "name": part.function_response.name,
                    "response": part.function_response.response,
                })
        save_message(
            str(uuid.uuid4()),
            _current_conversation_id,
            content_obj.role,
            content_text,
            json.dumps(calls) if calls else None,
            json.dumps(resolutions) if resolutions else None,
        )
    except Exception:
        logger.exception("Error saving chat history")

try:
    _load_history()
except Exception as e:
    print(f"Error loading chat history: {e}")


# ---------------------------------------------------------------------------
# Ollama fallback (Phase 2: Reliability)
# ---------------------------------------------------------------------------
def _ollama_models() -> list[str] | None:
    """Model tags the local Ollama has pulled, or None if it is unreachable."""
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return None
        return [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception:
        return None


def _model_is_pulled(model: str, available: list[str]) -> bool:
    """Ollama reports tags as `llama3:latest`; a config of `llama3` means that."""
    if not model:
        return False
    wanted = model if ":" in model else f"{model}:latest"
    return wanted in available or model in available


def _check_ollama_available() -> bool:
    """True only if Ollama can actually serve OLLAMA_MODEL.

    This used to check that the server answered /api/tags and nothing else, so
    a machine running Ollama without the configured model pulled passed the
    health check and then failed the real request with a bare 404. Every
    Gemini outage became "Error continuing conversation" instead of a fallback
    that says what to install.
    """
    available = _ollama_models()
    return available is not None and _model_is_pulled(OLLAMA_MODEL, available)

OLLAMA_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the text contents of a file so you can answer questions about it. Use after search_files locates a path. Large files are truncated; binary files cannot be read.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The absolute path of the file to read."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Renames a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "The absolute path of the file to rename."},
                    "destination": {"type": "string", "description": "The new absolute path."}
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Deletes a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The absolute path of the file to delete."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The absolute path of the file to write to."},
                    "content": {"type": "string", "description": "The text content to write."},
                    "mode": {"type": "string", "description": "'append' to add to the end of the file, or 'overwrite' to replace it entirely."}
                },
                "required": ["path", "content", "mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Finds indexed files whose FILENAME contains the keyword. Matches names only and cannot see inside files; use read_file on a returned path to inspect contents. Returns at most 20 matches, most recently modified first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "A partial filename or keyword to search for."}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "profile_data",
            "description": "Reads a CSV or Excel file and returns summary statistics, data types, and null counts. Use this to understand the structure and contents of a dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The filename or absolute path of the dataset (.csv or .xlsx)."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inline_chart",
            "description": "Reads a dataset and generates an inline chart (bar, line, scatter, hist). Returns the chart image to the user directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The dataset file path (.csv or .xlsx)."},
                    "chart_type": {"type": "string", "description": "Type of chart: 'bar', 'line', 'scatter', or 'hist'."},
                    "x_column": {"type": "string", "description": "Column for the X axis."},
                    "y_column": {"type": "string", "description": "Column for the Y axis (required for bar, line, scatter)."},
                    "title": {"type": "string", "description": "Optional title for the chart."}
                },
                "required": ["file_path", "chart_type", "x_column"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_watch_rule",
            "description": "Creates a watch rule to monitor a directory for files matching a glob pattern. The directory must already be in the whitelist. The only supported action is 'summarize'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "The absolute path of the directory to watch (must be whitelisted)."},
                    "pattern": {"type": "string", "description": "A file glob pattern, e.g. '*.pdf' or 'report_*.csv'."}
                },
                "required": ["directory", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_watch_rules",
            "description": "Lists all active watch rules (directory, pattern, and creation date).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_watch_rule",
            "description": "Deletes (deactivates) a watch rule by its numeric ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "integer", "description": "The ID of the watch rule to delete."}
                },
                "required": ["rule_id"]
            }
        }
    }
]


def _ollama_drive_tool_rounds(messages, tool_map, rounds: int = 0):
    """Keep calling Ollama until it answers in text or the budget runs out.

    The counterpart to _drive_tool_rounds on the Gemini side, and extracted
    for the same reason: confirming a mutating tool has to resume *into* the
    loop with the remaining budget rather than making one final call and
    ending the turn.

    Returns the answer text, or a dict carrying a tool_proposal when a
    mutating call needs confirmation (the pending globals are set first).
    """
    global _pending_ollama_messages, _pending_ollama_tool_calls, _pending_ollama_tool_map

    while True:
        # Withdrawing the tools on the last round forces a text answer
        # rather than a call that would have to be discarded -- the same
        # trick _drive_tool_rounds uses on the Gemini side.
        offer_tools = bool(tool_map) and rounds < MAX_TOOL_ROUNDS
        if not offer_tools and rounds >= MAX_TOOL_ROUNDS:
            logger.warning(
                "Ollama tool round budget (%d) exhausted; requesting a final "
                "text answer.", MAX_TOOL_ROUNDS,
            )

        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "tools": OLLAMA_TOOLS_SCHEMA if offer_tools else [],
        }
        if OLLAMA_OPTIONS:
            payload["options"] = dict(OLLAMA_OPTIONS)

        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT
        )
        resp.raise_for_status()
        message = resp.json().get("message", {})
        calls = message.get("tool_calls") or []

        # `not offer_tools` matters as much as `not calls`: on the final
        # round the tools were withdrawn, so any call the model still emits
        # is discarded rather than driving another iteration. Without it a
        # model that keeps calling loops forever despite the budget.
        if not calls or not tool_map or not offer_tools:
            content = message.get("content", "")
            if content:
                return content
            if rounds >= MAX_TOOL_ROUNDS:
                return (
                    f"I stopped after {MAX_TOOL_ROUNDS} tool steps without "
                    "reaching an answer. Try narrowing the request or asking "
                    "for one step at a time."
                )
            return "Error: Ollama returned an empty response."

        # The gate scans every call in the turn, not just the first: a
        # delete_file behind a search_files must still pause.
        mutating = _first_mutating(calls)
        if mutating is not None:
            name, args = call_name_and_args(mutating)
            _pending_ollama_messages = messages.copy()
            _pending_ollama_messages.append(message)
            _pending_ollama_tool_calls = calls
            _pending_ollama_tool_map = tool_map
            return {
                "tool_proposal": {
                    "name": name,
                    "args": args,
                    "diff": _build_tool_diff(mutating),
                }
            }

        rounds += 1
        last_ollama_turn["rounds"] = rounds
        messages.append(message)
        _record_ollama_calls(calls)

        results = []
        for call in calls:
            name, args = call_name_and_args(call)
            if name in tool_map:
                try:
                    result = tool_map[name](**args)
                except TypeError as e:
                    result = f"Argument Error: {e}"
                except Exception as e:
                    result = f"Python Execution Error: {e}"
            else:
                result = f"Error: Tool {name} not recognized."

            if (
                name == "inline_chart"
                and isinstance(result, str)
                and result.startswith("data:image")
            ):
                # The image goes to the caller and is replaced in the
                # transcript, where a base64 blob would be replayed every
                # turn. Keeping only the acknowledgement -- as this did before
                # -- meant the model told the user a chart had been sent that
                # was never delivered anywhere.
                last_ollama_turn["chart"] = result
                result = "Chart generated and sent to user successfully."

            results.append((name, str(result)))
            messages.append({"role": "tool", "name": name, "content": str(result)})

        _record_ollama_results(results)


def _record_ollama_calls(calls):
    """Put an Ollama tool-call turn into the transcript, in Gemini's shape.

    _chat_history is the single transcript both engines share, so a fallback
    turn has to be stored the same way -- otherwise switching back to Gemini
    mid-conversation replays a history with holes in it.
    """
    parts = []
    for call in calls:
        name, args = call_name_and_args(call)
        parts.append(types.Part.from_function_call(name=name, args=args))
    if not parts:
        return
    content = types.Content(role="model", parts=parts)
    _chat_history.append(content)
    _save_content(content)


def _record_ollama_results(results):
    """The matching tool-result turn for _record_ollama_calls."""
    parts = [
        types.Part.from_function_response(name=name, response={"result": text})
        for name, text in results
    ]
    if not parts:
        return
    content = types.Content(role="user", parts=parts)
    _chat_history.append(content)
    _save_content(content)


def _ollama_chat(
    system_prompt: str,
    user_message: str,
    tool_map: dict | None = None,
    history: list | None = None,
) -> str | dict:
    """Send a prompt to the local Ollama instance and return its response.

    Uses the /api/chat endpoint with proper message roles so Ollama
    receives the system prompt as a first-class instruction, not
    concatenated into the user message.

    Runs the same bounded tool loop the Gemini path does, so the fallback can
    search and then act on what it found. It previously executed
    `tool_calls[0]`, asked once more with tools removed, and stopped -- one
    tool per turn, no chaining, and any further call discarded.

    Args:
        system_prompt: The system instruction (candid or compliant).
        user_message:  The cleaned user message. Used only when `history` is
                       absent, since a transcript already ends with this turn.
        tool_map:      Dictionary of python functions for tools.
        history:       Budget-trimmed transcript to replay. Omitted by one-off
                       callers such as watch-rule summarisation, which have no
                       conversation to carry.

    Returns:
        The model's text response, or a dict containing a tool_proposal,
        or a descriptive error string.
    """
    available = _ollama_models()
    if available is None:
        return (
            "Error: Both Gemini and Ollama are unavailable. "
            "Gemini failed (see above), and Ollama is not running at "
            f"{OLLAMA_URL}. Start it with `ollama serve`."
        )
    if not _model_is_pulled(OLLAMA_MODEL, available):
        # Naming what *is* installed turns a dead end into one command.
        installed = ", ".join(sorted(available)) or "none"
        logger.warning(
            "Ollama is running but %s is not pulled; installed: %s",
            OLLAMA_MODEL, installed,
        )
        return (
            f"Error: Gemini failed (see above) and Ollama does not have the "
            f"configured model '{OLLAMA_MODEL}'. Run `ollama pull {OLLAMA_MODEL}`, "
            f"or point Lithe at one you already have (installed: {installed})."
        )

    global last_ollama_turn
    last_ollama_turn = {"rounds": 0, "chart": None}

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(to_ollama_messages(history))
    else:
        # No transcript to replay (watch-rule summarisation, and any caller
        # that wants a genuinely one-off answer).
        messages.append({"role": "user", "content": user_message})

    try:
        return _ollama_drive_tool_rounds(messages, tool_map)

    except httpx.TimeoutException:
        return (
            f"Error: Ollama request timed out after {OLLAMA_TIMEOUT}s. "
            "The model may be loading or the machine is under heavy load."
        )
    except Exception as e:
        return f"Error: Ollama fallback failed — {type(e).__name__}: {e}"

# Global state for safeword
session_safeword_active = False

def _check_hallucination(user_message: str, response_text: str, engine: str = "gemini") -> str | None:
    """Checks if the LLM hallucinated a tool execution when it shouldn't have."""
    if not response_text:
        return None
        
    user_msg = user_message.lower()
    resp_lower = response_text.lower()
    
    # 1. Mutating Intent
    mutating_intent = any(kw in user_msg for kw in ["create", "write", "rename", "delete", "make a file"]) and any(kw in user_msg for kw in ["file", ".txt", "folder"])
    claimed_success = any(kw in resp_lower for kw in ["i have created", "i've created", "is created", "has been created", "renamed", "deleted", "successfully", "done"])
    
    if mutating_intent and claimed_success:
        return "ERROR: The LLM generated a narrative claiming to have modified files, but failed to actually invoke the system tool. Please rephrase your request to explicitly command tool execution."

    # 2. Search Intent
    search_intent = any(kw in user_msg for kw in ["search", "find", "locate", "where is", "look for"]) and any(kw in user_msg for kw in ["file", "folder", "directory"])
    search_claimed = any(kw in resp_lower for kw in ["found", "here are the", "located", "matching files", "c:\\", "d:\\", "c:/", "d:/", "searched", "not present", "not found"])
    
    if search_intent and search_claimed:
        return "ERROR: The LLM generated a narrative claiming to have searched for files, but failed to actually invoke the system search tool. Please rephrase your request to explicitly command tool execution."

    return None




def _apply_file_context(system_prompt: str, cleaned_message: str) -> str:
    """Attach retrieved file content to the system prompt for this request.

    F-04 used to do ``cleaned_message += file_context``, so up to 100KB per
    named file became part of the user turn -- persisted to SQLite, reloaded at
    startup and re-sent on every subsequent request forever. Putting it in the
    system instruction instead means it is never written to the transcript at
    all, and is re-supplied each turn from a budgeted cache so that a follow-up
    like "now list its columns" still sees the file it refers to.

    Also stops file *content* being fed to _check_hallucination, which keyword-
    matches the user's message: a CSV containing the word "delete" could
    previously trip the mutating-intent guard.
    """
    global _context_blocks
    blocks, note = get_file_context_blocks(cleaned_message)

    # Re-appending a file already in the cache refreshes both its content and
    # its position, so the file under discussion is the last one evicted.
    for path, text in blocks:
        _context_blocks = [(p, t) for p, t in _context_blocks if p != path]
        _context_blocks.append((path, text))
    _context_blocks = trim_blocks(_context_blocks)

    sections = [system_prompt]
    if _context_blocks:
        sections.append("\n\n".join(text for _, text in _context_blocks))
    if note:
        # Deliberately not cached: "that file is not indexed" is a statement
        # about this turn's request, not a standing fact about the session.
        sections.append(note.strip())
    return "\n\n".join(sections)


def _abandon_pending_proposal():
    """Close out a tool proposal the user walked away from.

    Proposing a mutating tool puts a function_call in the transcript. If the
    next thing to happen is an ordinary message rather than a confirmation,
    that call never receives its response and the conversation carries a
    dangling call from then on. Answering it explicitly keeps the transcript
    valid and tells the model the operation did not run -- which matters,
    because otherwise it has no way to know whether the file was deleted.
    """
    global _pending_session, _pending_tool_calls, _pending_config
    global _pending_tool_map, _pending_rounds_used

    if not _pending_tool_calls:
        return

    logger.info(
        "Superseding an unconfirmed %s proposal; a new message arrived first.",
        _pending_tool_calls[0].name,
    )
    content = types.Content(
        role="user",
        parts=[
            types.Part.from_function_response(
                name=call.name,
                response={"result": (
                    "NOT EXECUTED: the user sent another message instead of "
                    "confirming, so this operation was cancelled."
                )},
            )
            for call in _pending_tool_calls
        ],
    )
    _chat_history.append(content)
    _save_content(content)

    _pending_session = None
    _pending_tool_calls = None
    _pending_config = None
    _pending_tool_map = None
    _pending_rounds_used = 0


# Tools that change the filesystem always pause for explicit user confirmation.
MUTATING_TOOLS = ("rename_file", "delete_file", "write_file")


def _build_tool_functions():
    """The tool closures offered to the model, defined once.

    chat() and chat_stream() each carried a byte-identical 100-line copy of
    these. That duplication is not hypothetical debt: it is what let the
    declared names drift from the dispatch map, leaving 5 of 9 tools
    unreachable on Gemini until it was found by the evaluation.

    The docstrings are the descriptions the model is given, and the
    __name__ of each closure is the name it is declared under, so both are
    load-bearing. tests/test_tool_contract.py pins them.

    _current_conversation_id is read from module scope at call time rather
    than captured, so a conversation switch is picked up without rebuilding
    the tools.
    """
    def rename_file(source: str, destination: str) -> str:
        """Renames a file or directory.
        Args:
            source: The absolute path of the file to rename.
            destination: The new absolute path.
        """
        return execute_rename(source, destination, safeword_active=True, conversation_id=_current_conversation_id)

    def delete_file(path: str) -> str:
        """Deletes a file or directory.
        Args:
            path: The absolute path of the file to delete.
        """
        return execute_delete(path, safeword_active=True, conversation_id=_current_conversation_id)

    def write_file(path: str, content: str, mode: str) -> str:
        """Writes content to a file.
        Args:
            path: The absolute path of the file to write to.
            content: The text content to write.
            mode: 'append' to add to the end of the file, or 'overwrite' to replace it entirely.
        """
        return execute_write(path, content, mode, safeword_active=True, conversation_id=_current_conversation_id)

    def search_files(keyword: str) -> str:
        """Finds indexed files whose FILENAME contains the keyword.

        This matches names only — it cannot see inside files. To answer a
        question about a file's contents, call this to locate the file and then
        call read_file on the path it returns. Returns at most 20 matches, most
        recently modified first.

        Args:
            keyword: A word or fragment appearing in the filename.
        """
        results = search_files_by_name(keyword)
        if not results:
            record_action("search_files", json.dumps({"keyword": keyword}), reversible=False, decision_outcome="auto-executed", execution_result="success (no results)", conversation_id=_current_conversation_id)
            return f"No files found matching '{keyword}' in the indexed directories."
        record_action("search_files", json.dumps({"keyword": keyword}), reversible=False, decision_outcome="auto-executed", execution_result=f"success ({len(results)} found)", conversation_id=_current_conversation_id)
        lines = []
        for r in results:
            size_kb = round(r['size_bytes'] / 1024, 1)
            cat = f" [{r['category']}]" if r.get('category') else ""
            lines.append(f"  {r['name']} ({size_kb} KB){cat} — {r['path']}")
        capped = " (showing the 20 most recently modified; there may be more)" if len(results) >= 20 else ""
        return f"Found {len(results)} file(s) matching '{keyword}'{capped}:\n" + "\n".join(lines)

    def read_file(path: str) -> str:
        """Reads the text contents of a file so you can answer questions about it.

        Use this after search_files has told you where a file is, or whenever the
        user asks what a file says. Large files are truncated with an explicit
        marker; binary files (PDF, images) cannot be read.

        Args:
            path: The absolute path of the file to read.
        """
        return execute_read(path, conversation_id=_current_conversation_id)

    def profile_data(file_path: str) -> str:
        """Reads a CSV or Excel file and returns summary statistics, data types, and null counts.
        Use this to understand the structure and contents of a dataset.
        Args:
            file_path: The filename or absolute path of the dataset (.csv or .xlsx).
        """
        return _profile_data(file_path, conversation_id=_current_conversation_id)

    def inline_chart(file_path: str, chart_type: str, x_column: str, y_column: str = "", title: str = "") -> str:
        """Reads a dataset and generates an inline chart (bar, line, scatter, hist).
        Returns the chart image to the user directly.
        Args:
            file_path: The dataset file path (.csv or .xlsx).
            chart_type: Type of chart: 'bar', 'line', 'scatter', or 'hist'.
            x_column: Column for the X axis.
            y_column: Column for the Y axis (required for bar, line, scatter).
            title: Optional title for the chart.
        """
        return _inline_chart(file_path, chart_type, x_column, y_column, title, conversation_id=_current_conversation_id)

    def create_watch_rule(directory: str, pattern: str) -> str:
        """Creates a watch rule to monitor a directory for files matching a glob pattern.
        The directory must already be in the whitelist. The only supported action is 'summarize'.
        Args:
            directory: The absolute path of the directory to watch (must be whitelisted).
            pattern: A file glob pattern, e.g. '*.pdf' or 'report_*.csv'.
        """
        return _create_watch_rule(directory, pattern, conversation_id=_current_conversation_id)

    def list_watch_rules() -> str:
        """Lists all active watch rules (directory, pattern, and creation date)."""
        return _list_watch_rules(conversation_id=_current_conversation_id)

    def delete_watch_rule(rule_id: int) -> str:
        """Deletes (deactivates) a watch rule by its numeric ID.
        Args:
            rule_id: The ID of the watch rule to delete.
        """
        return _delete_watch_rule(rule_id, conversation_id=_current_conversation_id)
    return [
        rename_file, delete_file, write_file, search_files, read_file,
        profile_data, inline_chart,
        create_watch_rule, list_watch_rules, delete_watch_rule,
    ]


def _first_mutating(calls):
    """The first call that needs confirmation, or None if they are all safe.

    `calls` may be Gemini function_call objects or Ollama's tool_call dicts;
    call_name_and_args reduces both so the two engines share one gate.
    """
    for call in calls or []:
        name, _ = call_name_and_args(call)
        if name in MUTATING_TOOLS:
            return call
    return None

# How many times the model may call a tool and be asked again within one turn.
# Bounded so a model that keeps calling tools cannot loop indefinitely.
MAX_TOOL_ROUNDS = 5


def _build_tool_diff(call) -> str:
    """A human-readable preview of what a mutating tool would do.

    Takes a call from either engine. _ollama_chat carried its own near-copy of
    this, which had already drifted: it wrote the whole file as additions when
    the target did not exist but used a different escape for the append case,
    and it never learned the errors="replace" guard that stops a file with odd
    bytes from raising inside the confirmation prompt.
    """
    name, args = call_name_and_args(call)

    if name == "delete_file":
        return f"- {args['path']}"

    if name == "rename_file":
        return f"- {args['source']}\n+ {args['destination']}"

    if name == "write_file":
        mode = args.get("mode", "overwrite")
        content = args.get("content", "")
        path = args["path"]
        if mode != "append" and os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                old_lines = f.readlines()
            new_lines = [
                line if line.endswith("\n") else line + "\n"
                for line in content.splitlines()
            ]
            return "\n".join(
                difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm="")
            )
        return "\n".join(f"+ {line}" for line in content.splitlines())

    return ""


def _execute_tool_calls(function_calls, tool_map):
    """Run each call and build the function_response parts to send back.

    Returns (parts, chart_data_uri). A chart is swapped for a short
    acknowledgement in the transcript, because a base64 image would otherwise be
    replayed to the model on every subsequent turn.
    """
    parts = []
    chart_data_uri = None

    for call in function_calls:
        if call.name in tool_map:
            try:
                result = tool_map[call.name](**call.args)
            except TypeError as e:
                result = f"Argument Error: {e}"
            except Exception as e:
                result = f"Python Execution Error: {e}"
        else:
            result = f"Error: Tool {call.name} not recognized."

        if call.name == "inline_chart" and isinstance(result, str) and result.startswith("data:image"):
            chart_data_uri = result
            result = "Chart generated and sent to user successfully."

        parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))

    return parts, chart_data_uri


def _tools_disabled(config):
    """A copy of `config` with tools removed, to force a final text answer."""
    try:
        return config.model_copy(update={"tools": None})
    except Exception:
        return config


def _drive_tool_rounds(response, contents, config, tool_map, rounds: int = 0):
    """Keep calling the model until it answers in text or the budget runs out.

    This is what makes Lithe an agent rather than a single tool-caller: the
    model can search, see the result, and act on it. Previously the follow-up
    response was returned as-is, so any tool call it contained was silently
    dropped.

    Returns (response, contents, chart_data_uri, proposal, rounds). A non-None
    proposal means a mutating tool needs confirmation; the pending globals have
    been set and the caller should hand it to the UI.
    """
    global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map
    global _pending_rounds_used

    chart_data_uri = None

    def record(content):
        """Add a turn to the request payload, the transcript and the DB at once.

        The callers used to resync with ``_chat_history = contents.copy()``
        after the fact. That silently discarded any history the request-time
        trim had left out, and it never wrote the intra-turn tool traffic to
        SQLite -- so a reload produced a function_response with no matching
        call, which Gemini rejects. Appending in one place keeps the three
        views consistent by construction.
        """
        contents.append(content)
        _chat_history.append(content)
        _save_content(content)

    while response.function_calls:
        # The first *mutating* call, not the first call. Gemini can emit
        # several in one turn, and _execute_tool_calls runs every one it is
        # given -- so checking only function_calls[0] meant a delete_file
        # sitting behind a search_files was executed with no confirmation at
        # all. The gate the whole design rests on was one parallel call away
        # from being bypassed.
        call = _first_mutating(response.function_calls) or response.function_calls[0]

        if call.name in MUTATING_TOOLS:
            _pending_session = contents.copy()
            # record() rather than a bare append: the proposal is a real turn,
            # and if it is not persisted the function_response saved on
            # confirmation reloads as an orphan.
            record(response.candidates[0].content)
            _pending_session.append(response.candidates[0].content)
            _pending_tool_calls = response.function_calls
            _pending_config = config
            _pending_tool_map = tool_map
            _pending_rounds_used = rounds
            proposal = {
                "tool_proposal": {
                    "name": call.name,
                    "args": call.args,
                    "diff": _build_tool_diff(call),
                }
            }
            return response, contents, chart_data_uri, proposal, rounds

        if rounds >= MAX_TOOL_ROUNDS:
            # Ask once more with no tools available, so the model is forced to
            # answer in text instead of emitting a call that would be discarded.
            logger.warning(
                "Tool round budget (%d) exhausted; requesting a final text answer.",
                MAX_TOOL_ROUNDS,
            )
            response = _client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=_tools_disabled(config)
            )
            break

        rounds += 1
        record(response.candidates[0].content)
        parts, chart = _execute_tool_calls(response.function_calls, tool_map)
        if chart:
            chart_data_uri = chart
        record(types.Content(role="user", parts=parts))
        response = _client.models.generate_content(
            model=GEMINI_MODEL, contents=contents, config=config
        )

    return response, contents, chart_data_uri, None, rounds


def chat(user_message: str) -> str:
    """Send a message to the Gemini LLM and return its response.

    Automatically detects the safeword in the user's input to select
    the appropriate system prompt (candid vs. compliant).
    Handles function calling synchronously.

    Args:
        user_message: The raw text from the user.

    Returns:
        The model's text response.
    """
    # --- F-06: Safeword detection ---
    safeword_active, cleaned_message = detect_safeword(user_message)
    global session_safeword_active
    if session_safeword_active:
        safeword_active = True

    # A proposal left unconfirmed would otherwise dangle in the transcript.
    _abandon_pending_proposal()

    # --- F-04: Inject File Context (into the system prompt, not the turn) ---
    system_prompt = _apply_file_context(
        COMPLIANT_SYSTEM_PROMPT if safeword_active else CANDID_SYSTEM_PROMPT,
        cleaned_message,
    )

    # --- F-05: Dynamic Tool Wrappers ---
    tools = _build_tool_functions()
    # Keyed by __name__ because that is exactly what the Gemini SDK uses when it
    # builds the FunctionDeclaration, so a tool can never be advertised under a
    # name this map cannot resolve.
    tool_map = {fn.__name__: fn for fn in tools}

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        max_output_tokens=2048,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    # --- Initialize conversation history for this request ---
    global _chat_history
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=cleaned_message)]
    )
    _chat_history.append(user_content)
    _save_content(user_content)
    # A trimmed *view* of the transcript: _chat_history stays whole in
    # memory, but an old conversation is not re-sent in full every turn.
    contents = trim_history(_chat_history)

    # --- Call Gemini ---
    try:
        global active_engine
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        active_engine = "gemini"

        # --- Tool rounds: run until the model answers in text ---
        response, contents, chart_data_uri, proposal, rounds = _drive_tool_rounds(
            response, contents, config, tool_map
        )
        if proposal:
            return proposal

        if rounds == 0:
            # No tool ran, so check the model did not merely claim it had.
            err = _check_hallucination(cleaned_message, response.text, "gemini")
            if err:
                return err


        # Update telemetry
        if response.usage_metadata:
            global last_token_counts
            last_token_counts = {
                "prompt": response.usage_metadata.prompt_token_count,
                "candidates": response.usage_metadata.candidates_token_count,
                "total": response.usage_metadata.total_token_count
            }

        # No resync from `contents` here: _drive_tool_rounds already appended
        # every intra-turn message to _chat_history. Copying the payload back
        # would delete whatever the request-time trim had left out.
        model_content = response.candidates[0].content
        _chat_history.append(model_content)
        _save_content(model_content)

        # response.text is None when the final turn carried no text part — a
        # safety block, an empty candidate, or a model still trying to call
        # tools after the budget ran out. Never hand None back to the caller.
        answer = response.text or ""
        if not answer.strip():
            if rounds >= MAX_TOOL_ROUNDS:
                answer = (
                    f"I stopped after {MAX_TOOL_ROUNDS} tool steps without reaching an "
                    "answer. Try narrowing the request or asking for one step at a time."
                )
            else:
                answer = "I wasn't able to produce an answer for that. Please try rephrasing."

        if chart_data_uri:
            return {"chart": chart_data_uri, "text": answer}
        return answer

    except (errors.APIError, httpx.TimeoutException, httpx.TransportError) as e:
        # Gemini is genuinely unreachable or refused the request: fall back.
        active_engine = "ollama"
        logger.warning(
            "Gemini unavailable (%s): %s — falling back to Ollama (%s @ %s)",
            type(e).__name__, e, OLLAMA_MODEL, OLLAMA_URL,
        )
        # The transcript already ends with this turn, so the fallback replays
        # it rather than being handed a lone message with no context.
        ollama_response = _ollama_chat(
            system_prompt, cleaned_message, tool_map, history=trim_history(_chat_history)
        )
        
        if isinstance(ollama_response, dict) and "tool_proposal" in ollama_response:
            return ollama_response

        # Only meaningful when no tool ran. Unconditionally, it destroyed
        # correct answers: the guard keys on words like "found" and "located",
        # so a genuine search_files result came back to the user as
        # "ERROR: ... failed to actually invoke the system search tool".
        # The Gemini path has always gated it on rounds == 0; this had not.
        if last_ollama_turn["rounds"] == 0:
            err = _check_hallucination(cleaned_message, ollama_response, "ollama")
            if err:
                ollama_response = err

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=ollama_response)]
        )
        _chat_history.append(model_content)
        _save_content(model_content)
        if last_ollama_turn["chart"]:
            return {"chart": last_ollama_turn["chart"], "text": ollama_response}
        return ollama_response

    except Exception as e:
        # Anything else is a defect in Lithe, not a connectivity problem. The
        # old handler caught bare Exception and rerouted to Ollama, so a KeyError
        # on a missing tool argument, a UnicodeDecodeError in the diff builder or
        # an IndexError on a blocked response all reported as "Gemini connection
        # failed" and silently switched engines. Surface it instead.
        logger.exception("Internal error while handling a chat turn: %s", e)
        return (
            f"Internal error in Lithe ({type(e).__name__}: {e}). "
            "This is a bug rather than a connection problem — see backend.log."
        )


def chat_stream(user_message: str):
    """Stream tokens from the Gemini LLM as they're generated.

    Yields dicts suitable for SSE serialization:
        {"type": "token", "content": "..."}   — a text delta
        {"type": "tool_proposal", "proposal": {...}} — mutating tool needs confirmation
        {"type": "done", "tokens": {...}}     — stream finished, telemetry attached

    The tool-proposal interception logic mirrors chat(): mutating tools pause
    execution and store pending state; read-only tools execute immediately.
    """
    # --- F-06: Safeword detection ---
    safeword_active, cleaned_message = detect_safeword(user_message)
    global session_safeword_active
    if session_safeword_active:
        safeword_active = True

    # A proposal left unconfirmed would otherwise dangle in the transcript.
    _abandon_pending_proposal()

    # --- F-04: Inject File Context (into the system prompt, not the turn) ---
    system_prompt = _apply_file_context(
        COMPLIANT_SYSTEM_PROMPT if safeword_active else CANDID_SYSTEM_PROMPT,
        cleaned_message,
    )

    # --- F-05: Dynamic Tool Wrappers (same as chat()) ---
    tools = _build_tool_functions()
    # Keyed by __name__ because that is exactly what the Gemini SDK uses when it
    # builds the FunctionDeclaration, so a tool can never be advertised under a
    # name this map cannot resolve.
    tool_map = {fn.__name__: fn for fn in tools}

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        max_output_tokens=2048,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    # --- Build conversation history ---
    global _chat_history
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=cleaned_message)]
    )
    _chat_history.append(user_content)
    _save_content(user_content)
    # A trimmed *view* of the transcript: _chat_history stays whole in
    # memory, but an old conversation is not re-sent in full every turn.
    contents = trim_history(_chat_history)

    try:
        global active_engine
        # --- Stream from Gemini ---
        accumulated_text = ""
        accumulated_function_calls = []

        stream = _client.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        active_engine = "gemini"

        last_response = None
        for chunk in stream:
            last_response = chunk
            # Yield text deltas
            if chunk.text:
                accumulated_text += chunk.text
                yield {"type": "token", "content": chunk.text}
            # Accumulate function calls (typically in the last chunk)
            if chunk.function_calls:
                accumulated_function_calls.extend(chunk.function_calls)

        # --- Handle function calls after stream completes ---
        if accumulated_function_calls:
            # As in _drive_tool_rounds: the confirmation gate must consider
            # every call in the turn, not just the first one.
            call = (
                _first_mutating(accumulated_function_calls)
                or accumulated_function_calls[0]
            )

            # Rebuild the model turn from the streamed pieces.
            model_parts = []
            if accumulated_text:
                model_parts.append(types.Part.from_text(text=accumulated_text))
            for fc in accumulated_function_calls:
                model_parts.append(types.Part.from_function_call(name=fc.name, args=fc.args))
            model_content = types.Content(role="model", parts=model_parts)

            if call.name in MUTATING_TOOLS:
                # Mutating tool — pause for confirmation.
                global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map
                global _pending_rounds_used

                _pending_session = contents.copy()
                _pending_session.append(model_content)
                _pending_tool_calls = accumulated_function_calls
                _pending_config = config
                _pending_tool_map = tool_map
                _pending_rounds_used = 0

                _chat_history.append(model_content)
                _save_content(model_content)

                yield {"type": "tool_proposal", "proposal": {
                    "name": call.name,
                    "args": call.args,
                    "diff": _build_tool_diff(call),
                }}
                return  # Stop the generator — tool needs confirmation

            # Non-mutating tools execute immediately, then the loop continues so
            # the model can act on what came back rather than being cut off.
            contents.append(model_content)
            _chat_history.append(model_content)
            _save_content(model_content)
            parts, chart = _execute_tool_calls(accumulated_function_calls, tool_map)
            if chart:
                yield {"type": "chart", "data_uri": chart}
            tool_result_content = types.Content(role="user", parts=parts)
            contents.append(tool_result_content)
            _chat_history.append(tool_result_content)
            _save_content(tool_result_content)

            followup = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            followup, contents, later_chart, proposal, _ = _drive_tool_rounds(
                followup, contents, config, tool_map, rounds=1
            )
            if later_chart:
                yield {"type": "chart", "data_uri": later_chart}
            if proposal:
                yield {"type": "tool_proposal", "proposal": proposal["tool_proposal"]}
                return


            followup_text = followup.text or ""
            if followup_text:
                yield {"type": "token", "content": followup_text}
                accumulated_text += followup_text

            # Update telemetry from follow-up
            if followup.usage_metadata:
                global last_token_counts
                last_token_counts = {
                    "prompt": followup.usage_metadata.prompt_token_count,
                    "candidates": followup.usage_metadata.candidates_token_count,
                    "total": followup.usage_metadata.total_token_count
                }

            full_model = types.Content(
                role="model",
                parts=[types.Part.from_text(text=followup_text)]
            )
            _chat_history.append(full_model)
            _save_content(full_model)

            yield {"type": "done", "tokens": last_token_counts}
            return

        # --- No function calls — pure text response ---
        err = _check_hallucination(cleaned_message, accumulated_text, "gemini")
        if err:
            yield {"type": "token", "content": "\n\n" + err}

        # Update telemetry from last chunk
        if last_response and last_response.usage_metadata:
            last_token_counts = {
                "prompt": last_response.usage_metadata.prompt_token_count,
                "candidates": last_response.usage_metadata.candidates_token_count,
                "total": last_response.usage_metadata.total_token_count
            }

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=accumulated_text)]
        )
        _chat_history.append(model_content)
        _save_content(model_content)

        yield {"type": "done", "tokens": last_token_counts}

    except (errors.APIError, httpx.TimeoutException, httpx.TransportError) as e:
        # Gemini is genuinely unreachable or refused the request: fall back.
        active_engine = "ollama"
        logger.warning(
            "Gemini streaming unavailable (%s): %s — falling back to Ollama (%s @ %s)",
            type(e).__name__, e, OLLAMA_MODEL, OLLAMA_URL,
        )
        # The transcript already ends with this turn, so the fallback replays
        # it rather than being handed a lone message with no context.
        ollama_response = _ollama_chat(
            system_prompt, cleaned_message, tool_map, history=trim_history(_chat_history)
        )
        
        if isinstance(ollama_response, dict) and "tool_proposal" in ollama_response:
            yield {"type": "tool_proposal", "proposal": ollama_response["tool_proposal"]}
            return

        # See chat(): the guard is only meaningful when no tool ran.
        if last_ollama_turn["rounds"] == 0:
            err = _check_hallucination(cleaned_message, ollama_response, "ollama")
            if err:
                ollama_response = err

        if last_ollama_turn["chart"]:
            yield {"type": "chart", "data_uri": last_ollama_turn["chart"]}

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=ollama_response)]
        )
        _chat_history.append(model_content)
        _save_content(model_content)
        # Yield entire Ollama response as a single token chunk
        yield {"type": "token", "content": ollama_response}
        yield {"type": "done", "tokens": last_token_counts}

    except Exception as e:
        # See the matching branch in chat(): a defect must not masquerade as a
        # connection failure and silently change engines.
        logger.exception("Internal error while streaming a chat turn: %s", e)
        yield {
            "type": "token",
            "content": (
                f"Internal error in Lithe ({type(e).__name__}: {e}). "
                "This is a bug rather than a connection problem — see backend.log."
            ),
        }
        yield {"type": "done", "tokens": last_token_counts}


def handle_tool_response(accept: bool) -> dict | str:
    """Resumes the pending session after user accepts or rejects a tool."""
    global active_engine

    if active_engine == "ollama":
        global _pending_ollama_messages, _pending_ollama_tool_calls, _pending_ollama_tool_map
        if not _pending_ollama_messages or not _pending_ollama_tool_calls:
            return "Error: No pending Ollama tool call found."

        # Every pending call, not just [0]. The gate now pauses on the first
        # *mutating* call in the turn, which may sit behind a read-only one --
        # so resolving only [0] would run the wrong tool and never run the one
        # the user actually confirmed.
        messages = _pending_ollama_messages
        pending_calls = _pending_ollama_tool_calls
        tool_map = _pending_ollama_tool_map

        results = []
        for call in pending_calls:
            name, args = call_name_and_args(call)
            if accept:
                if name in tool_map:
                    try:
                        result = tool_map[name](**args)
                    except TypeError as e:
                        result = f"Argument Error: {e}"
                    except Exception as e:
                        result = f"Python Execution Error: {e}"
                else:
                    result = f"Error: Tool {name} not recognized."
            else:
                result = (
                    "ERROR: The user REJECTED this operation. Acknowledge this "
                    "and ask what else you can do."
                )
                record_action(
                    name, json.dumps(args), reversible=False,
                    decision_outcome="rejected", execution_result="User rejected",
                    conversation_id=_current_conversation_id,
                )

            results.append((name, str(result)))
            messages.append({"role": "tool", "name": name, "content": str(result)})

        _record_ollama_calls(pending_calls)
        _record_ollama_results(results)

        _pending_ollama_messages = None
        _pending_ollama_tool_calls = None
        _pending_ollama_tool_map = None

        try:
            # Resume *into* the loop rather than making one final call, so
            # "delete this, then tell me what's left" does not stop at the
            # delete. rounds=1 charges the confirmed step against the budget.
            answer = _ollama_drive_tool_rounds(messages, tool_map, rounds=1)
            if isinstance(answer, dict):
                # Another mutating tool needs confirmation; the driver has
                # already re-armed the pending state.
                return answer

            model_content = types.Content(
                role="model", parts=[types.Part.from_text(text=answer)]
            )
            _chat_history.append(model_content)
            _save_content(model_content)
            answer = answer or "Error: Ollama returned an empty followup response."
            if last_ollama_turn["chart"]:
                return {"chart": last_ollama_turn["chart"], "text": answer}
            return answer
        except Exception as e:
            _pending_ollama_messages = None
            _pending_ollama_tool_calls = None
            _pending_ollama_tool_map = None
            return f"Error continuing Ollama conversation: {str(e)}"


    # --- Gemini Path ---
    # _chat_history is no longer in this list: nothing here rebinds it since
    # the `_chat_history = session.copy()` resync was removed, and declaring it
    # global after the Ollama branch above has already appended to it is a
    # syntax error.
    global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map, _pending_rounds_used
    if not _pending_session or not _pending_tool_calls:
        return "Error: No pending tool call found."

    function_responses = []
    
    for call in _pending_tool_calls:
        if accept:
            if call.name in _pending_tool_map:
                try:
                    result = _pending_tool_map[call.name](**call.args)
                except TypeError as e:
                    result = f"Argument Error: {e}"
                except Exception as e:
                    result = f"Python Execution Error: {e}"
            else:
                result = f"Error: Tool {call.name} not recognized."
        else:
            result = "ERROR: The user REJECTED this operation. Acknowledge this and ask what else you can do."
            if isinstance(call.args, dict):
                args_dict = call.args
            else:
                args_dict = dict(call.args.items()) if hasattr(call.args, 'items') else {}
            record_action(call.name, json.dumps(args_dict), reversible=False, decision_outcome="rejected", execution_result="User rejected", conversation_id=_current_conversation_id)

        function_responses.append(
            types.Part.from_function_response(
                name=call.name,
                response={"result": result}
            )
        )

    user_tool_content = types.Content(
        role="user",
        parts=function_responses
    )
    _pending_session.append(user_tool_content)
    _chat_history.append(user_tool_content)
    _save_content(user_tool_content)

    try:
        session = _pending_session
        config = _pending_config
        tool_map = _pending_tool_map
        rounds_used = _pending_rounds_used

        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=session,
            config=config,
        )
        active_engine = "gemini"

        # Resume the tool loop with the budget the paused turn had left, so a
        # confirmed tool can be followed by further steps instead of ending the
        # turn at whatever the model happened to say next.
        response, session, chart_data_uri, proposal, _ = _drive_tool_rounds(
            response, session, config, tool_map, rounds_used
        )
        if proposal:
            # Another mutating tool needs confirmation; _drive_tool_rounds has
            # already re-armed the pending state, so leave it in place.
            return proposal

        # Update telemetry
        if response.usage_metadata:
            global last_token_counts
            last_token_counts = {
                "prompt": response.usage_metadata.prompt_token_count,
                "candidates": response.usage_metadata.candidates_token_count,
                "total": response.usage_metadata.total_token_count
            }

        # As in chat(): the resumed rounds already recorded themselves, and
        # `session` is only the request payload -- copying it back over the
        # transcript would drop anything the trim had excluded.
        model_content = response.candidates[0].content
        _chat_history.append(model_content)
        _save_content(model_content)

        # Clear state
        _pending_session = None
        _pending_tool_calls = None
        _pending_config = None
        _pending_tool_map = None
        _pending_rounds_used = 0

        answer = response.text or "Done."
        if chart_data_uri:
            return {"chart": chart_data_uri, "text": answer}
        return answer
    except Exception as e:
        _pending_session = None
        return f"Error continuing conversation: {str(e)}"


def summarize_file_for_watch_rule(file_path: str, rule_id: int) -> str:
    """
    Standalone, one-off summarization call for the file watcher.
    """
    import pandas as pd
    
    try:
        # Check size cap and read file
        try:
            stat = os.stat(file_path)
            size = stat.st_size
        except Exception as e:
            return f"Error reading file info: {e}"
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.csv', '.xlsx', '.xls']:
            nrows = 5000 if size > MAX_FILE_SIZE_BYTES else None
            try:
                if ext == '.csv':
                    df = pd.read_csv(file_path, nrows=nrows)
                else:
                    df = pd.read_excel(file_path, nrows=nrows)
                file_content = df.head(nrows or 50).to_string() if not df.empty else "Empty file."
            except Exception as e:
                return f"Error parsing data file: {e}"
        else:
            file_content, is_truncated = read_file_securely(file_path)
            if file_content.startswith("[Binary or Unsupported"):
                # Skip gracefully
                return "Skipped (Binary or Unsupported)"
                
        prompt = f"Please summarize the following file ({os.path.basename(file_path)}):\n\n{file_content}"
        
        if _client:
            try:
                response = _client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=CANDID_SYSTEM_PROMPT
                    )
                )
                summary = response.text
            except Exception:
                # Fallback
                response = _ollama_chat(CANDID_SYSTEM_PROMPT, prompt)
                summary = response if isinstance(response, str) else response.get('text', str(response))
        else:
            response = _ollama_chat(CANDID_SYSTEM_PROMPT, prompt)
            summary = response if isinstance(response, str) else response.get('text', str(response))
            
        # A failed/empty summary — or an error string bubbled up from the Ollama
        # fallback — must stay in action_history only. Never broadcast it to the
        # chat window.
        summary = (summary or "").strip()
        if not summary or summary.startswith("Error:"):
            error_msg = summary or "Failed to generate summary."
            record_action(
                "watch_rule_summary",
                json.dumps({"file_path": file_path, "rule_id": rule_id}),
                reversible=False,
                decision_outcome="auto-executed",
                execution_result=f"error: {error_msg}",
                conversation_id=""
            )
            return error_msg

        summary_id = insert_auto_summary(rule_id, file_path, summary)
        from src.backend.broadcaster import broadcast_event
        broadcast_event("auto_summary", path=file_path, id=summary_id, summary=summary, rule_id=rule_id)
        record_action(
            "watch_rule_summary",
            json.dumps({"file_path": file_path, "rule_id": rule_id}),
            reversible=False,
            decision_outcome="auto-executed",
            execution_result="success",
            conversation_id=""
        )
        return summary
        
    except Exception as e:
        record_action(
            "watch_rule_summary",
            json.dumps({"file_path": file_path, "rule_id": rule_id}),
            reversible=False,
            decision_outcome="auto-executed",
            execution_result=f"error: {str(e)}",
            conversation_id=""
        )
        return f"Error: {str(e)}"


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Lithe — Brain Smoke Test")
    print("=" * 60)

    # Test 1: Candid mode
    test_prompt = "What is Lithe?"
    print(f"\n[CANDID MODE] Prompt: {test_prompt!r}")
    print("-" * 40)
    result = chat(test_prompt)
    print(result)

    # Test 2: Safeword mode
    test_prompt_override = "Override Lithe — Just say hello."
    print(f"\n[COMPLIANT MODE] Prompt: {test_prompt_override!r}")
    print("-" * 40)
    result_override = chat(test_prompt_override)
    print(result_override)

    print("\n" + "=" * 60)
    print("Smoke test complete.")
    print("=" * 60)
