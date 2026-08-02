"""
Lithe — OS Tools (F-05: Basic Task Execution)

Provides system-level functions (rename, delete) to the Gemini LLM.
Enforces the safeword permission requirement: if the safeword is not
active, these functions immediately return a permission error instructing
the LLM to ask the user for authorization.
"""

import os


def execute_rename(source: str, destination: str, safeword_active: bool) -> str:
    """
    Executes a file or directory rename/move operation.
    """
    if not safeword_active:
        return (
            "ERROR: User permission required. Tell the user you cannot execute "
            "this action without explicit permission. Instruct them to repeat "
            "their request and include the safeword 'Override Lithe'."
        )

    if not os.path.exists(source):
        return f"ERROR: Source path '{source}' does not exist."

    try:
        os.rename(source, destination)
        return f"SUCCESS: Renamed/moved '{source}' to '{destination}'."
    except Exception as e:
        return f"ERROR: Failed to rename file: {str(e)}"


def execute_delete(path: str, safeword_active: bool) -> str:
    """
    Executes a file deletion operation.
    """
    if not safeword_active:
        return (
            "ERROR: User permission required. Tell the user you cannot execute "
            "this action without explicit permission. Instruct them to repeat "
            "their request and include the safeword 'Override Lithe'."
        )

    if not os.path.exists(path):
        return f"ERROR: Path '{path}' does not exist."

    try:
        if os.path.isdir(path):
            os.rmdir(path)
            return f"SUCCESS: Deleted directory '{path}'."
        else:
            os.remove(path)
            return f"SUCCESS: Deleted file '{path}'."
    except Exception as e:
        return f"ERROR: Failed to delete path: {str(e)}"
