"""
Lithe — Directory Indexer (F-03)

Crawls whitelisted directories using os.walk, applying strict exclusions
for heavy or hidden folders, and extracts file metadata for storage in
the SQLite memory layer.

Phase 3: Now applies heuristic category tags to each file during indexing.
"""

import os
import time
from typing import Any, Dict, List

from src.backend.config import INDEX_WHITELIST
from src.backend.memory import upsert_files
from src.backend.heuristics import categorize_path
from src.backend.broadcaster import broadcast_event

# Strict exclusions for directory names (do not traverse into these).
# Shared with watcher.py to keep filtering consistent.
EXCLUDED_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".idea",
    ".vscode",
}

# Relevant file extensions for R&D (optional, currently we index everything but can filter later)
# PRIORITIZED_EXTENSIONS = {".csv", ".pdf", ".py", ".json", ".md", ".txt", ".ts", ".tsx"}

BATCH_SIZE = 500


def walk_and_index() -> int:
    """
    Walks all directories in INDEX_WHITELIST, extracts file metadata,
    applies heuristic category tags, and upserts into the SQLite database
    in batches.
    
    Returns:
        The total number of files indexed.
    """
    if not INDEX_WHITELIST:
        print("[Lithe Indexer] INDEX_WHITELIST is empty. Nothing to index.")
        return 0

    total_indexed = 0
    current_batch: List[Dict[str, Any]] = []
    current_time = time.time()

    for root_dir in INDEX_WHITELIST:
        total_indexed += walk_and_index_path(root_dir, _batch=current_batch)

    # Upsert any remaining files
    if current_batch:
        upsert_files(current_batch)

    print(f"[Lithe Indexer] Indexing complete. Indexed {total_indexed} files.")
    return total_indexed

def walk_and_index_path(root_dir: str, _batch: List[Dict[str, Any]] = None) -> int:
    """Indexes a single root directory."""
    if not os.path.exists(root_dir):
        print(f"[Lithe Indexer] Warning: Directory not found: {root_dir}")
        return 0

    current_time = time.time()
    total_indexed = 0
    is_root_call = _batch is None
    batch = _batch if not is_root_call else []

    for dirpath, dirnames, filenames in os.walk(root_dir):
            # Modify dirnames in-place to prevent os.walk from entering excluded directories
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                
                try:
                    stat = os.stat(file_path)
                    _, ext = os.path.splitext(filename)
                    
                    file_record = {
                        "path": file_path,
                        "name": filename,
                        "extension": ext.lower() if ext else "",
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "indexed_at": current_time,
                        "category": categorize_path(file_path),
                    }
                    
                    batch.append(file_record)
                    total_indexed += 1
                    broadcast_event("indexed", file_path)
                    
                    if len(batch) >= BATCH_SIZE:
                        upsert_files(batch)
                        batch.clear()
                        
                except Exception as e:
                    # Catch permission errors or missing files during walk
                    print(f"[Lithe Indexer] Error processing {file_path}: {e}")

    # If this was called standalone, commit the remaining batch
    if is_root_call and batch:
        upsert_files(batch)

    return total_indexed

if __name__ == "__main__":
    # Allow running directly from terminal
    walk_and_index()
