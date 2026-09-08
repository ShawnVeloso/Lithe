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

from src.backend.config import (
    INDEX_WHITELIST,
    EXCLUDED_EXTENSIONS,
    CONTENT_INDEXED_EXTENSIONS,
    CONTENT_INDEX_MAX_BYTES,
)
from src.backend.memory import (
    upsert_files,
    get_all_files_mtime,
    delete_files_by_paths,
    upsert_file_content,
    paths_missing_content,
)
from src.backend.heuristics import categorize_path
from src.backend.broadcaster import broadcast_event
from src.backend.logger import logger

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


def index_file_content(file_path: str, ext: str) -> bool:
    """Put a file's searchable text in the content index. True if it was stored.

    Only the head of a file is indexed (CONTENT_INDEX_MAX_BYTES), matching what
    retrieval will actually show. A file whose match lies past that boundary is
    not found, which is the honest failure: the alternative is reporting a match
    the model then cannot quote.

    Never raises. Indexing walks a user's real drive, where an unreadable file
    is ordinary -- a lock, a permission, a name the filesystem accepts and the
    decoder does not -- and one of them must not end the walk.
    """
    if ext not in CONTENT_INDEXED_EXTENSIONS:
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="strict") as handle:
            content = handle.read(CONTENT_INDEX_MAX_BYTES)
    except (UnicodeDecodeError, OSError, ValueError):
        # A file with a text extension that does not decode is not text. Left
        # out rather than stored as replacement characters, which would match
        # nothing a user would ever search for.
        return False
    if not content.strip():
        return False
    try:
        upsert_file_content(file_path, content)
    except Exception:
        logger.warning("Could not index the content of %s", file_path, exc_info=True)
        return False
    return True


def walk_and_index() -> int:
    """
    Walks all directories in INDEX_WHITELIST, extracts file metadata,
    applies heuristic category tags, and upserts into the SQLite database
    in batches.
    
    Implements Startup Reconciliation: compares current files with database
    records to only process changed files, and deletes removed/excluded files.
    """
    if not INDEX_WHITELIST:
        print("[Lithe Indexer] INDEX_WHITELIST is empty. Nothing to index.")
        return 0

    total_indexed = 0
    current_batch: List[Dict[str, Any]] = []
    
    # Fetch existing files for reconciliation
    db_files = get_all_files_mtime()
    counters = {"new": 0, "unchanged": 0, "content": 0}

    # Which already-known files have no searchable content yet. Computed once
    # rather than queried per file: on a real drive this is one query against
    # tens of thousands of paths instead of tens of thousands of queries.
    backfill = set(paths_missing_content(list(db_files.keys())))

    for root_dir in INDEX_WHITELIST:
        total_indexed += walk_and_index_path(
            root_dir, 
            _batch=current_batch, 
            _db_files=db_files, 
            _counters=counters,
            _backfill=backfill,
        )

    # Upsert any remaining files in the batch
    if current_batch:
        upsert_files(current_batch)

    # Any files left in db_files were not found during the walk (deleted)
    # or are now excluded by EXCLUDED_EXTENSIONS.
    removed_count = len(db_files)
    if removed_count > 0:
        delete_files_by_paths(list(db_files.keys()))

    print(
        f"[Lithe Indexer] reconciled: {counters['new']} new/modified, "
        f"{removed_count} removed, {counters['unchanged']} unchanged, "
        f"{counters.get('content', 0)} content-indexed."
    )
    return total_indexed

def walk_and_index_path(
    root_dir: str, 
    _batch: List[Dict[str, Any]] = None, 
    _db_files: Dict[str, float] = None,
    _counters: Dict[str, int] = None,
    _backfill: set = None,
) -> int:
    """Indexes a single root directory."""
    if not os.path.exists(root_dir):
        print(f"[Lithe Indexer] Warning: Directory not found: {root_dir}")
        return 0

    current_time = time.time()
    total_indexed = 0
    is_root_call = _batch is None
    batch = _batch if not is_root_call else []
    counters = _counters if _counters is not None else {"new": 0, "unchanged": 0}

    for dirpath, dirnames, filenames in os.walk(root_dir):
            # Modify dirnames in-place to prevent os.walk from entering excluded directories
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                _, ext = os.path.splitext(filename)
                ext = ext.lower() if ext else ""

                if ext in EXCLUDED_EXTENSIONS:
                    # File is excluded. Do not pop from _db_files so it gets deleted
                    continue
                
                try:
                    stat = os.stat(file_path)
                    
                    # Reconciliation check
                    if _db_files is not None:
                        if file_path in _db_files:
                            db_mtime = _db_files.pop(file_path)
                            if stat.st_mtime == db_mtime:
                                counters["unchanged"] += 1
                                # An unchanged file still needs its content read
                                # if it was indexed before the content index
                                # existed. Without this an existing install
                                # never backfills: reconciliation skips every
                                # file it already knows, so content search stays
                                # empty until something edits each file.
                                if file_path in (_backfill or ()):
                                    if index_file_content(file_path, ext):
                                        counters["content"] = counters.get("content", 0) + 1
                                continue
                    
                    file_record = {
                        "path": file_path,
                        "name": filename,
                        "extension": ext,
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "indexed_at": current_time,
                        "category": categorize_path(file_path),
                    }
                    
                    batch.append(file_record)
                    total_indexed += 1
                    counters["new"] += 1
                    if index_file_content(file_path, ext):
                        counters["content"] = counters.get("content", 0) + 1
                    
                    if is_root_call:
                        # Only broadcast if this is a live manual addition, not during startup bulk scan
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
