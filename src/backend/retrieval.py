"""
Lithe — Retrieval Engine (F-04: RAG & File Context)

Extracts file mentions from user prompts, resolves them via SQLite,
and reads their content to inject as context into the LLM prompt.
"""

import os
import re
from typing import List, Tuple

from src.backend.memory import find_file_paths

# Max file size to read (100KB) to prevent blowing up the LLM context
MAX_FILE_SIZE_BYTES = 100 * 1024

def extract_filenames(text: str) -> List[str]:
    """
    Uses regex to extract potential filenames with extensions from the text.
    E.g., "Summarize budget.csv" -> ["budget.csv"]
    """
    # Matches words with extensions (e.g., file.txt, script.py)
    # Assumes filename characters: alphanumerics, dashes, underscores
    pattern = r"\b[\w-]+\.[A-Za-z0-9]+\b"
    matches = re.findall(pattern, text)
    # Return unique matches
    return list(set(matches))


def read_file_securely(filepath: str) -> Tuple[str, bool]:
    """
    Reads the content of a file. Truncates if it exceeds MAX_FILE_SIZE_BYTES.
    Returns (content, is_truncated).
    """
    try:
        stat = os.stat(filepath)
        size = stat.st_size
        
        with open(filepath, "r", encoding="utf-8") as f:
            if size > MAX_FILE_SIZE_BYTES:
                content = f.read(MAX_FILE_SIZE_BYTES)
                return content + "\n... [FILE TRUNCATED DUE TO SIZE]", True
            else:
                return f.read(), False
    except UnicodeDecodeError:
        return "[Binary or Unsupported File Format]", False
    except Exception as e:
        return f"[Error reading file: {str(e)}]", False


def get_file_contexts(user_message: str) -> str:
    """
    Main entrypoint for F-04.
    Finds files mentioned in the prompt, reads them, and formats a context block.
    """
    filenames = extract_filenames(user_message)
    if not filenames:
        return ""

    file_paths = find_file_paths(filenames)
    if not file_paths:
        # We detected filenames, but they aren't indexed.
        # Add a system note so the LLM knows we couldn't find them.
        missing = ", ".join(filenames)
        return f"\n\n[System Note: The following files were mentioned but not found in the indexed directories: {missing}]"

    context_blocks = []
    
    for path in file_paths:
        filename = os.path.basename(path)
        content, _ = read_file_securely(path)
        
        block = f"--- LOCAL FILE CONTEXT: {filename} ---\n"
        block += f"Filepath: {path}\n"
        block += f"{content}\n"
        block += "-" * 40
        context_blocks.append(block)

    if not context_blocks:
        return ""

    return "\n\n" + "\n\n".join(context_blocks)
