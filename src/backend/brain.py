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
from src.backend.memory import search_files_by_name

# Global state for pausing execution during tool confirmation
_pending_session: list[types.Content] | None = None
_pending_tool_calls = None
_pending_config = None
_pending_tool_map = None

# Global state for telemetry
last_token_counts = {"prompt": 0, "candidates": 0, "total": 0}
active_engine = "gemini"

# ---------------------------------------------------------------------------
# Gemini client (initialized once at module load)
# ---------------------------------------------------------------------------
_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'timeout': 5.0})


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


def _ollama_chat(system_prompt: str, user_message: str) -> str:
    """Send a prompt to the local Ollama instance and return its response.

    Uses the /api/chat endpoint with proper message roles so Ollama
    receives the system prompt as a first-class instruction, not
    concatenated into the user message.

    Args:
        system_prompt: The system instruction (candid or compliant).
        user_message:  The cleaned user message (with file context injected).

    Returns:
        The model's text response, or a descriptive error string.
    """
    if not _check_ollama_available():
        return (
            "Error: Both Gemini and Ollama are unavailable. "
            "Gemini failed (see above), and Ollama is not running at "
            f"{OLLAMA_URL}. Start Ollama with `ollama serve` and ensure "
            f"the '{OLLAMA_MODEL}' model is pulled (`ollama pull {OLLAMA_MODEL}`)."
        )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
    }

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "")
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
        return execute_rename(source, destination, safeword_active=True)

    def delete_file(path: str) -> str:
        """Deletes a file or directory.
        Args:
            path: The absolute path of the file to delete.
        """
        return execute_delete(path, safeword_active=True)

    def write_file(path: str, content: str, mode: str) -> str:
        """Writes content to a file.
        Args:
            path: The absolute path of the file to write to.
            content: The text content to write.
            mode: 'append' to add to the end of the file, or 'overwrite' to replace it entirely.
        """
        return execute_write(path, content, mode, safeword_active=True)

    def search_files(keyword: str) -> str:
        """Searches the local file index for files matching a keyword.
        You MUST call this tool whenever the user asks which files contain a word, 
        or asks to locate files, even if they don't know the exact filename or extension.
        Args:
            keyword: A partial filename or keyword to search for.
        """
        results = search_files_by_name(keyword)
        if not results:
            return f"No files found matching '{keyword}' in the indexed directories."
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
    )

    # --- Initialize conversation history for this request ---
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=cleaned_message)]
        )
    ]

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
                _pending_session = contents
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

        # Update telemetry
        if response.usage_metadata:
            global last_token_counts
            last_token_counts = {
                "prompt": response.usage_metadata.prompt_token_count,
                "candidates": response.usage_metadata.candidates_token_count,
                "total": response.usage_metadata.total_token_count
            }

        return response.text

    except (errors.APIError, httpx.TimeoutException, Exception) as e:
        active_engine = "ollama"
        error_name = type(e).__name__
        print(f"[Lithe] Gemini connection failed ({error_name}): {e}")
        print(f"[Lithe] Routing prompt to local Ollama fallback ({OLLAMA_MODEL} @ {OLLAMA_URL})...")
        return _ollama_chat(system_prompt, cleaned_message)


def handle_tool_response(accept: bool) -> dict | str:
    """Resumes the pending session after user accepts or rejects a tool."""
    global _pending_session, _pending_tool_calls, _pending_config, _pending_tool_map
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

        function_responses.append(
            types.Part.from_function_response(
                name=call.name,
                response={"result": result}
            )
        )

    _pending_session.append(
        types.Content(
            role="user",
            parts=function_responses
        )
    )

    try:
        global active_engine
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
