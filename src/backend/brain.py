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
from src.backend.retrieval import get_file_contexts
from src.backend.tools import execute_rename, execute_delete, execute_write
from src.backend.memory import search_files_by_name, record_action

# Global state for pausing execution during tool confirmation
_pending_session: list[types.Content] | None = None
_pending_tool_calls = None
_pending_config = None
_pending_tool_map = None

_pending_ollama_messages = None
_pending_ollama_tool_calls = None
_pending_ollama_tool_map = None

# Global state for conversation history
_chat_history: list[types.Content] = []
_current_conversation_id: str | None = None

# Global state for telemetry
last_token_counts = {"prompt": 0, "candidates": 0, "total": 0}
active_engine = "gemini"

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
from src.backend.memory import save_message, get_chat_history, get_latest_conversation_id

def _load_history():
    global _chat_history
    global _current_conversation_id
    
    _chat_history.clear()
    
    _current_conversation_id = get_latest_conversation_id()
    if not _current_conversation_id:
        _current_conversation_id = str(uuid.uuid4())
        return

    for row in get_chat_history(_current_conversation_id):
        parts = []
        if row["content"]:
            parts.append(types.Part.from_text(text=row["content"]))
        if row["tool_proposal_json"]:
            call_data = json.loads(row["tool_proposal_json"])
            parts.append(types.Part.from_function_call(name=call_data["name"], args=call_data["args"]))
        if row["tool_resolution"]:
            res_data = json.loads(row["tool_resolution"])
            parts.append(types.Part.from_function_response(name=res_data["name"], response=res_data["response"]))
        
        if parts:
            _chat_history.append(types.Content(role=row["role"], parts=parts))

def new_conversation() -> str:
    """Starts a new conversation by resetting the global state."""
    global _chat_history
    global _current_conversation_id
    _chat_history.clear()
    _current_conversation_id = str(uuid.uuid4())
    return _current_conversation_id

def _save_content(content_obj: types.Content):
    try:
        content_text = ""
        tool_proposal_json = None
        tool_resolution = None
        for part in content_obj.parts:
            if part.text:
                content_text += part.text
            elif part.function_call:
                tool_proposal_json = json.dumps({"name": part.function_call.name, "args": part.function_call.args})
            elif part.function_response:
                tool_resolution = json.dumps({"name": part.function_response.name, "response": part.function_response.response})
        save_message(str(uuid.uuid4()), _current_conversation_id, content_obj.role, content_text, tool_proposal_json, tool_resolution)
    except Exception as e:
        print(f"Error saving chat history: {e}")

try:
    _load_history()
except Exception as e:
    print(f"Error loading chat history: {e}")


# ---------------------------------------------------------------------------
# Ollama fallback (Phase 2: Reliability)
# ---------------------------------------------------------------------------
def _check_ollama_available() -> bool:
    """Quick health check — returns True if Ollama is reachable."""
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, Exception):
        return False

OLLAMA_TOOLS_SCHEMA = [
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
            "description": "Searches the local file index for files matching a keyword. You MUST call this tool whenever the user asks which files contain a word, or asks to locate files, even if they don't know the exact filename or extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "A partial filename or keyword to search for."}
                },
                "required": ["keyword"]
            }
        }
    }
]


def _ollama_chat(system_prompt: str, user_message: str, tool_map: dict | None = None) -> str | dict:
    """Send a prompt to the local Ollama instance and return its response.

    Uses the /api/chat endpoint with proper message roles so Ollama
    receives the system prompt as a first-class instruction, not
    concatenated into the user message.
    Handles function calling synchronously via Ollama's native tool support.

    Args:
        system_prompt: The system instruction (candid or compliant).
        user_message:  The cleaned user message (with file context injected).
        tool_map:      Dictionary of python functions for tools.

    Returns:
        The model's text response, or a dict containing a tool_proposal,
        or a descriptive error string.
    """
    if not _check_ollama_available():
        return (
            "Error: Both Gemini and Ollama are unavailable. "
            "Gemini failed (see above), and Ollama is not running at "
            f"{OLLAMA_URL}. Start Ollama with `ollama serve` and ensure "
            f"the '{OLLAMA_MODEL}' model is pulled (`ollama pull {OLLAMA_MODEL}`)."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "tools": OLLAMA_TOOLS_SCHEMA if tool_map else []
    }

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message", {})
        
        # --- Handle Function Calls ---
        if "tool_calls" in message and tool_map:
            # We only support one function call at a time for simplicity in the UI
            call = message["tool_calls"][0]
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            
            # --- Check if it's a mutating tool that needs confirmation ---
            if name in ["rename_file", "delete_file", "write_file"]:
                global _pending_ollama_messages, _pending_ollama_tool_calls, _pending_ollama_tool_map
                _pending_ollama_messages = messages.copy()
                _pending_ollama_messages.append(message)
                _pending_ollama_tool_calls = message["tool_calls"]
                _pending_ollama_tool_map = tool_map
                
                # Generate diff string
                diff_str = ""
                if name == "delete_file":
                    diff_str = f"- {args.get('path', '')}"
                elif name == "rename_file":
                    diff_str = f"- {args.get('source', '')}\n+ {args.get('destination', '')}"
                elif name == "write_file":
                    import os
                    mode = args.get("mode", "overwrite")
                    content = args.get("content", "")
                    if mode == "append":
                        diff_str = "\n".join(f"+ {line}" for line in content.splitlines())
                    else:
                        path = args.get("path", "")
                        if os.path.exists(path):
                            with open(path, 'r', encoding='utf-8') as f:
                                old_lines = f.readlines()
                            new_lines = [line + '\n' if not line.endswith('\n') else line for line in content.splitlines()]
                            diff = difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm='')
                            diff_str = "\n".join(diff)
                        else:
                            diff_str = "\n".join(f"+ {line}" for line in content.splitlines())

                return {
                    "tool_proposal": {
                        "name": name,
                        "args": args,
                        "diff": diff_str
                    }
                }
                
            # Non-mutating tools execute immediately
            messages.append(message)
            if name in tool_map:
                try:
                    result = tool_map[name](**args)
                except TypeError as e:
                    result = f"Argument Error: {e}"
                except Exception as e:
                    result = f"Python Execution Error: {e}"
            else:
                result = f"Error: Tool {name} not recognized."
                
            messages.append({
                "role": "tool",
                "content": str(result)
            })
            
            # Call Ollama a second time for final answer
            followup_payload = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False
            }
            resp_followup = httpx.post(
                f"{OLLAMA_URL}/api/chat",
                json=followup_payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp_followup.raise_for_status()
            content = resp_followup.json().get("message", {}).get("content", "")
            return content or "Error: Ollama returned an empty followup response."

        # No function calls
        content = message.get("content", "")
        if not content:
            return "Error: Ollama returned an empty response."
        return content

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

    # --- F-04: Inject File Context ---
    file_context = get_file_contexts(cleaned_message)
    if file_context:
        cleaned_message += file_context

    system_prompt = (
        COMPLIANT_SYSTEM_PROMPT if safeword_active else CANDID_SYSTEM_PROMPT
    )

    # --- F-05: Dynamic Tool Wrappers ---
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
        """Searches the local file index for files matching a keyword.
        You MUST call this tool whenever the user asks which files contain a word, 
        or asks to locate files, even if they don't know the exact filename or extension.
        Args:
            keyword: A partial filename or keyword to search for.
        """
        print(f"[TOOL EXECUTED] search_files: {keyword}")
        results = search_files_by_name(keyword)
        import json
        if not results:
            record_action("search_files", json.dumps({"keyword": keyword}), reversible=False, decision_outcome="auto-executed", execution_result="success (no results)", conversation_id=_current_conversation_id)
            return f"No files found matching '{keyword}' in the indexed directories."
        record_action("search_files", json.dumps({"keyword": keyword}), reversible=False, decision_outcome="auto-executed", execution_result=f"success ({len(results)} found)", conversation_id=_current_conversation_id)
        lines = []
        for r in results:
            size_kb = round(r['size_bytes'] / 1024, 1)
            cat = f" [{r['category']}]" if r.get('category') else ""
            lines.append(f"  {r['name']} ({size_kb} KB){cat} — {r['path']}")
        return f"Found {len(results)} file(s) matching '{keyword}':\n" + "\n".join(lines)

    tools = [rename_file, delete_file, write_file, search_files]
    tool_map = {
        "rename_file": rename_file,
        "delete_file": delete_file,
        "write_file": write_file,
        "search_files": search_files,
    }

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
    contents = _chat_history.copy()

    # --- Call Gemini ---
    try:
        global active_engine
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        active_engine = "gemini"

        # --- Handle potential Function Calls ---
        if response.function_calls:
            # We only support one function call at a time for simplicity in the UI
            call = response.function_calls[0]
            
            # --- Check if it's a mutating tool that needs confirmation ---
            if call.name in ["rename_file", "delete_file", "write_file"]:
                global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map
                _pending_session = contents.copy()
                _pending_session.append(response.candidates[0].content)
                _pending_tool_calls = response.function_calls
                _pending_config = config
                _pending_tool_map = tool_map
                
                # Generate diff string
                diff_str = ""
                if call.name == "delete_file":
                    diff_str = f"- {call.args['path']}"
                elif call.name == "rename_file":
                    diff_str = f"- {call.args['source']}\n+ {call.args['destination']}"
                elif call.name == "write_file":
                    import os
                    mode = call.args.get("mode", "overwrite")
                    content = call.args.get("content", "")
                    if mode == "append":
                        diff_str = "\n".join(f"+ {line}" for line in content.splitlines())
                    else:
                        path = call.args['path']
                        if os.path.exists(path):
                            with open(path, 'r', encoding='utf-8') as f:
                                old_lines = f.readlines()
                            new_lines = [line + '\n' if not line.endswith('\n') else line for line in content.splitlines()]
                            diff = difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm='')
                            diff_str = "\n".join(diff)
                        else:
                            diff_str = "\n".join(f"+ {line}" for line in content.splitlines())

                return {
                    "tool_proposal": {
                        "name": call.name,
                        "args": call.args,
                        "diff": diff_str
                    }
                }

            # Non-mutating tools execute immediately
            contents.append(response.candidates[0].content)
            function_responses = []
            for call in response.function_calls:
                # Execute the python function mapped to the tool name
                if call.name in tool_map:
                    try:
                        result = tool_map[call.name](**call.args)
                    except TypeError as e:
                        result = f"Argument Error: {e}"
                    except Exception as e:
                        result = f"Python Execution Error: {e}"
                else:
                    result = f"Error: Tool {call.name} not recognized."

                # Append the result to the responses
                function_responses.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": result}
                    )
                )

            # Append the function responses as the user's reply
            contents.append(
                types.Content(
                    role="user",
                    parts=function_responses
                )
            )

            # Call Gemini a second time to generate the final text answer
            response = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
        else:
            # Check for hallucinated execution
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

        _chat_history = contents.copy()
        model_content = response.candidates[0].content
        _chat_history.append(model_content)
        _save_content(model_content)

        return response.text

    except (errors.APIError, httpx.TimeoutException, Exception) as e:
        active_engine = "ollama"
        error_name = type(e).__name__
        print(f"[Lithe] Gemini connection failed ({error_name}): {e}")
        print(f"[Lithe] Routing prompt to local Ollama fallback ({OLLAMA_MODEL} @ {OLLAMA_URL})...")
        ollama_response = _ollama_chat(system_prompt, cleaned_message, tool_map)
        
        if isinstance(ollama_response, dict) and "tool_proposal" in ollama_response:
            return ollama_response

        err = _check_hallucination(cleaned_message, ollama_response, "ollama")
        if err:
            ollama_response = err

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=ollama_response)]
        )
        _chat_history.append(model_content)
        _save_content(model_content)
        return ollama_response


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

    # --- F-04: Inject File Context ---
    file_context = get_file_contexts(cleaned_message)
    if file_context:
        cleaned_message += file_context

    system_prompt = (
        COMPLIANT_SYSTEM_PROMPT if safeword_active else CANDID_SYSTEM_PROMPT
    )

    # --- F-05: Dynamic Tool Wrappers (same as chat()) ---
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
        """Searches the local file index for files matching a keyword.
        You MUST call this tool whenever the user asks which files contain a word,
        or asks to locate files, even if they don't know the exact filename or extension.
        Args:
            keyword: A partial filename or keyword to search for.
        """
        print(f"[TOOL EXECUTED] search_files: {keyword}")
        results = search_files_by_name(keyword)
        import json
        if not results:
            record_action("search_files", json.dumps({"keyword": keyword}), reversible=False, decision_outcome="auto-executed", execution_result="success (no results)", conversation_id=_current_conversation_id)
            return f"No files found matching '{keyword}' in the indexed directories."
        record_action("search_files", json.dumps({"keyword": keyword}), reversible=False, decision_outcome="auto-executed", execution_result=f"success ({len(results)} found)", conversation_id=_current_conversation_id)
        lines = []
        for r in results:
            size_kb = round(r['size_bytes'] / 1024, 1)
            cat = f" [{r['category']}]" if r.get('category') else ""
            lines.append(f"  {r['name']} ({size_kb} KB){cat} — {r['path']}")
        return f"Found {len(results)} file(s) matching '{keyword}':\n" + "\n".join(lines)

    tools = [rename_file, delete_file, write_file, search_files]
    tool_map = {
        "rename_file": rename_file,
        "delete_file": delete_file,
        "write_file": write_file,
        "search_files": search_files,
    }

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
    contents = _chat_history.copy()

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
            call = accumulated_function_calls[0]

            if call.name in ["rename_file", "delete_file", "write_file"]:
                # Mutating tool — pause for confirmation
                global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map

                # Build the model content from accumulated stream
                model_parts = []
                if accumulated_text:
                    model_parts.append(types.Part.from_text(text=accumulated_text))
                for fc in accumulated_function_calls:
                    model_parts.append(types.Part.from_function_call(
                        name=fc.name, args=fc.args
                    ))
                model_content = types.Content(role="model", parts=model_parts)

                _pending_session = contents.copy()
                _pending_session.append(model_content)
                _pending_tool_calls = accumulated_function_calls
                _pending_config = config
                _pending_tool_map = tool_map

                # Generate diff string
                diff_str = ""
                if call.name == "delete_file":
                    diff_str = f"- {call.args['path']}"
                elif call.name == "rename_file":
                    diff_str = f"- {call.args['source']}\n+ {call.args['destination']}"
                elif call.name == "write_file":
                    import os as _os
                    mode = call.args.get("mode", "overwrite")
                    content = call.args.get("content", "")
                    if mode == "append":
                        diff_str = "\n".join(f"+ {line}" for line in content.splitlines())
                    else:
                        path = call.args['path']
                        if _os.path.exists(path):
                            with open(path, 'r', encoding='utf-8') as f:
                                old_lines = f.readlines()
                            new_lines = [line + '\n' if not line.endswith('\n') else line for line in content.splitlines()]
                            diff = difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm='')
                            diff_str = "\n".join(diff)
                        else:
                            diff_str = "\n".join(f"+ {line}" for line in content.splitlines())

                # Save the model content to history
                _chat_history = contents.copy()
                _chat_history.append(model_content)
                _save_content(model_content)

                yield {"type": "tool_proposal", "proposal": {
                    "name": call.name,
                    "args": call.args,
                    "diff": diff_str
                }}
                return  # Stop the generator — tool needs confirmation

            # Non-mutating tools — execute immediately
            model_parts = []
            if accumulated_text:
                model_parts.append(types.Part.from_text(text=accumulated_text))
            for fc in accumulated_function_calls:
                model_parts.append(types.Part.from_function_call(
                    name=fc.name, args=fc.args
                ))
            model_content = types.Content(role="model", parts=model_parts)
            contents.append(model_content)

            function_responses = []
            for fc in accumulated_function_calls:
                if fc.name in tool_map:
                    try:
                        result = tool_map[fc.name](**fc.args)
                    except TypeError as e:
                        result = f"Argument Error: {e}"
                    except Exception as e:
                        result = f"Python Execution Error: {e}"
                else:
                    result = f"Error: Tool {fc.name} not recognized."
                function_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result}
                    )
                )

            contents.append(types.Content(role="user", parts=function_responses))

            # Follow-up call (non-streaming — tool results are short)
            followup = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

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

            _chat_history = contents.copy()
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
        _chat_history = contents.copy()
        _chat_history.append(model_content)
        _save_content(model_content)

        yield {"type": "done", "tokens": last_token_counts}

    except (errors.APIError, httpx.TimeoutException, Exception) as e:
        active_engine = "ollama"
        error_name = type(e).__name__
        print(f"[Lithe] Gemini streaming failed ({error_name}): {e}")
        print(f"[Lithe] Routing prompt to local Ollama fallback ({OLLAMA_MODEL} @ {OLLAMA_URL})...")
        ollama_response = _ollama_chat(system_prompt, cleaned_message, tool_map)
        
        if isinstance(ollama_response, dict) and "tool_proposal" in ollama_response:
            yield {"type": "tool_proposal", "proposal": ollama_response["tool_proposal"]}
            return

        err = _check_hallucination(cleaned_message, ollama_response, "ollama")
        if err:
            ollama_response = err

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=ollama_response)]
        )
        _chat_history.append(model_content)
        _save_content(model_content)
        # Yield entire Ollama response as a single token chunk
        yield {"type": "token", "content": ollama_response}
        yield {"type": "done", "tokens": last_token_counts}


def handle_tool_response(accept: bool) -> dict | str:
    """Resumes the pending session after user accepts or rejects a tool."""
    global active_engine

    if active_engine == "ollama":
        global _pending_ollama_messages, _pending_ollama_tool_calls, _pending_ollama_tool_map
        if not _pending_ollama_messages or not _pending_ollama_tool_calls:
            return "Error: No pending Ollama tool call found."

        call = _pending_ollama_tool_calls[0]
        name = call["function"]["name"]
        args = call["function"]["arguments"]

        if accept:
            if name in _pending_ollama_tool_map:
                try:
                    result = _pending_ollama_tool_map[name](**args)
                except TypeError as e:
                    result = f"Argument Error: {e}"
                except Exception as e:
                    result = f"Python Execution Error: {e}"
            else:
                result = f"Error: Tool {name} not recognized."
        else:
            result = "ERROR: The user REJECTED this operation. Acknowledge this and ask what else you can do."
            import json
            record_action(name, json.dumps(args), reversible=False, decision_outcome="rejected", execution_result="User rejected", conversation_id=_current_conversation_id)

        _pending_ollama_messages.append({
            "role": "tool",
            "content": str(result)
        })

        try:
            resp = httpx.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": _pending_ollama_messages,
                    "stream": False
                },
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "")
            
            # Clear state
            _pending_ollama_messages = None
            _pending_ollama_tool_calls = None
            _pending_ollama_tool_map = None
            
            return content or "Error: Ollama returned an empty followup response."
        except Exception as e:
            _pending_ollama_messages = None
            _pending_ollama_tool_calls = None
            _pending_ollama_tool_map = None
            return f"Error continuing Ollama conversation: {str(e)}"


    # --- Gemini Path ---
    global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map, _chat_history
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
            import json
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
    _save_content(user_tool_content)

    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_pending_session,
            config=_pending_config,
        )
        active_engine = "gemini"
        
        # Update telemetry
        if response.usage_metadata:
            global last_token_counts
            last_token_counts = {
                "prompt": response.usage_metadata.prompt_token_count,
                "candidates": response.usage_metadata.candidates_token_count,
                "total": response.usage_metadata.total_token_count
            }

        _chat_history = _pending_session.copy()
        model_content = response.candidates[0].content
        _chat_history.append(model_content)
        _save_content(model_content)

        # Clear state
        _pending_session = None
        _pending_tool_calls = None
        _pending_config = None
        _pending_tool_map = None
        return response.text
    except Exception as e:
        _pending_session = None
        return f"Error continuing conversation: {str(e)}"


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
