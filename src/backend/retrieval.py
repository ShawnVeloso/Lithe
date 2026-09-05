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

    # An all-digit extension is a version number, not a file: "python 3.11",
    # "v2.0", "version 1.4". Those used to be looked up and, of course, not
    # found, which glued a "not found in the indexed directories" note onto an
    # ordinary question and told the model a file was missing that the user had
    # never mentioned. Extensions keep their digits otherwise, so .7z and .mp3
    # still resolve.
    matches = [m for m in matches if not m.rsplit(".", 1)[1].isdigit()]

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


def get_file_context_blocks(user_message: str) -> Tuple[List[Tuple[str, str]], str]:
    """Resolve files named in the prompt into individually addressable blocks.

    Returns ``(blocks, note)`` where ``blocks`` is a list of ``(path, text)``
    pairs and ``note`` is a system note naming files that were mentioned but
    are not in the index (empty when there are none).

    The caller needs the blocks separately rather than pre-joined into one
    string so it can cache them per file and evict them individually under a
    budget. Before this existed the joined string was glued onto the user's
    message and persisted with it, which is what let file context grow without
    limit -- see context_budget.
    """
    filenames = extract_filenames(user_message)
    if not filenames:
        return [], ""

    file_paths = find_file_paths(filenames)
    if not file_paths:
        # We detected filenames, but they aren't indexed.
        # Add a system note so the LLM knows we couldn't find them.
        missing = ", ".join(filenames)
        return [], (
            "\n\n[System Note: The following files were mentioned but not found "
            f"in the indexed directories: {missing}]"
        )

    blocks = []
    for path in file_paths:
        filename = os.path.basename(path)
        content, _ = read_file_securely(path)

        block = f"--- LOCAL FILE CONTEXT: {filename} ---\n"
        block += f"Filepath: {path}\n"
        block += f"{content}\n"
        block += "-" * 40
        blocks.append((path, block))

    return blocks, ""


def get_file_contexts(user_message: str) -> str:
    """
    Main entrypoint for F-04.
    Finds files mentioned in the prompt, reads them, and formats a context block.
    """
    blocks, note = get_file_context_blocks(user_message)
    if note:
        return note
    if not blocks:
        return ""

    return "\n\n" + "\n\n".join(text for _, text in blocks)
