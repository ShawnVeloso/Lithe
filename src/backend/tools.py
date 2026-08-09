"""
Lithe — OS Tools (F-05: Basic Task Execution)

Provides system-level functions (rename, delete) to the Gemini LLM.
Enforces the safeword permission requirement: if the safeword is not
active, these functions immediately return a permission error instructing
the LLM to ask the user for authorization.

Safety features (Phase 1 — Circuit Breakers):
  - Path validation: rejects empty, null-byte, and protected system paths.
  - Timeout wrapper: all OS operations run inside a 30-second hard timeout
    via concurrent.futures to prevent hung filesystem calls.
"""

import os
import concurrent.futures
import json
from src.backend.memory import record_action

# ---------------------------------------------------------------------------
# Circuit Breaker configuration
# ---------------------------------------------------------------------------

# Hard timeout for any single tool operation (seconds)
TOOL_TIMEOUT_SECONDS = 30

# Directories that tools must NEVER modify
PROTECTED_PATHS = [
    os.path.normcase(r"C:\Windows"),
    os.path.normcase(r"C:\Program Files"),
    os.path.normcase(r"C:\Program Files (x86)"),
    os.path.normcase(os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "")),
]


def _validate_path(path: str, label: str = "path") -> str | None:
    """Validates and normalizes a file path.

    Returns:
        An error string if the path is invalid, or None if it's safe.
    """
    if not path or not path.strip():
        return f"ERROR: {label} is empty."
    if "\x00" in path:
        return f"ERROR: {label} contains invalid null bytes."

    real = os.path.normcase(os.path.realpath(path))
    for protected in PROTECTED_PATHS:
        if real.startswith(protected):
            return f"ERROR: Refusing to modify protected system path: {path}"
    return None


def _run_with_timeout(fn, *args):
    """Runs a callable with a hard timeout.

    Returns:
        The function's return value, or an error string on timeout.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        try:
            return future.result(timeout=TOOL_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            return (
                f"ERROR: Operation timed out after {TOOL_TIMEOUT_SECONDS} seconds. "
                "The target path may be on a network drive or locked by another process."
            )


# ---------------------------------------------------------------------------
# Tool functions (exposed to the LLM via function calling)
# ---------------------------------------------------------------------------

def execute_rename(source: str, destination: str, safeword_active: bool) -> str:
    """
    Executes a file or directory rename/move operation.
    """
    print(f"[TOOL EXECUTED] rename_file: {source} -> {destination}")
    if not safeword_active:
        return (
            "ERROR: User permission required. Tell the user you cannot execute "
            "this action without explicit permission. Instruct them to repeat "
            "their request and include the safeword 'Override Lithe'."
        )

    # --- Circuit Breaker: validate arguments ---
    src_err = _validate_path(source, "source")
    if src_err:
        return src_err
    dst_err = _validate_path(destination, "destination")
    if dst_err:
        return dst_err

    if not os.path.exists(source):
        return f"ERROR: Source path '{source}' does not exist."

    def _do_rename():
        os.rename(source, destination)
        record_action(
            "rename_file",
            json.dumps({"source": source, "destination": destination}),
            reversible=True
        )
        return f"SUCCESS: Renamed/moved '{source}' to '{destination}'."

    try:
        return _run_with_timeout(_do_rename)
    except Exception as e:
        return f"ERROR: Failed to rename file: {str(e)}"


def execute_delete(path: str, safeword_active: bool) -> str:
    """
    Executes a file deletion operation.
    """
    print(f"[TOOL EXECUTED] delete_file: {path}")
    if not safeword_active:
        return (
            "ERROR: User permission required. Tell the user you cannot execute "
            "this action without explicit permission. Instruct them to repeat "
            "their request and include the safeword 'Override Lithe'."
        )

    # --- Circuit Breaker: validate arguments ---
    path_err = _validate_path(path, "path")
    if path_err:
        return path_err

    if not os.path.exists(path):
        return f"ERROR: Path '{path}' does not exist."

    def _do_delete():
        if os.path.isdir(path):
            os.rmdir(path)
            record_action(
                "delete_file",
                json.dumps({"path": path, "is_dir": True}),
                reversible=False
            )
            return f"SUCCESS: Deleted directory '{path}'."
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            os.remove(path)
            record_action(
                "delete_file",
                json.dumps({"path": path, "is_dir": False, "content": content}),
                reversible=True
            )
            return f"SUCCESS: Deleted file '{path}'."

    try:
        return _run_with_timeout(_do_delete)
    except Exception as e:
        return f"ERROR: Failed to delete path: {str(e)}"

def execute_write(path: str, content: str, mode: str, safeword_active: bool) -> str:
    """
    Executes a file write operation (append or overwrite).
    """
    print(f"[TOOL EXECUTED] write_file: {path}")
    # Note: we check safeword in brain.py instead now, but keeping the signature
    # for consistency until the unified diff flow replaces it.
    
    # --- Circuit Breaker: validate arguments ---
    path_err = _validate_path(path, "path")
    if path_err:
        return path_err

    if mode not in ["append", "overwrite"]:
        return f"ERROR: Invalid mode '{mode}'. Must be 'append' or 'overwrite'."

    def _do_write():
        file_mode = "a" if mode == "append" else "w"
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        is_new_file = not os.path.exists(path)
        old_content = None
        if not is_new_file and mode == "overwrite":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                old_content = f.read()
        elif not is_new_file and mode == "append":
            # For append, we could just read the whole file or track length.
            # To keep it simple and reversible, we just save the whole old content.
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                old_content = f.read()
                
        with open(path, file_mode, encoding="utf-8") as f:
            f.write(content)
            
        record_action(
            "write_file",
            json.dumps({"path": path, "is_new": is_new_file, "old_content": old_content}),
            reversible=True
        )
        return f"SUCCESS: Wrote to file '{path}' in {mode} mode."

    try:
        return _run_with_timeout(_do_write)
    except Exception as e:
        return f"ERROR: Failed to write to file: {str(e)}"
