"""
Lithe — File System Watcher (Phase 3: Event-Driven Memory)

Watches whitelisted directories for real-time file changes using the
`watchdog` library. When a file is created, modified, deleted, or moved,
the SQLite memory database is updated automatically — no restart needed.

Events are debounced with a 1-second delay to handle rapid IDE saves
(temp file → rename patterns) without hammering the database.
"""

import os
import time
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from src.backend.config import INDEX_WHITELIST
from src.backend.indexer import EXCLUDED_DIRS
from src.backend.memory import upsert_files, delete_file_by_path
from src.backend.heuristics import categorize_path


class _LitheEventHandler(FileSystemEventHandler):
    """Handles file system events and syncs changes to the SQLite database."""

    # Debounce delay in seconds
    DEBOUNCE_SECONDS = 1.0

    def __init__(self):
        super().__init__()
        self._pending: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Watchdog event callbacks
    # ------------------------------------------------------------------

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and not self._is_excluded(event.src_path):
            self._schedule("upsert", event.src_path)

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and not self._is_excluded(event.src_path):
            self._schedule("upsert", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and not self._is_excluded(event.src_path):
            self._schedule("delete", event.src_path)

    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            if not self._is_excluded(event.src_path):
                self._schedule("delete", event.src_path)
            if hasattr(event, "dest_path") and not self._is_excluded(event.dest_path):
                self._schedule("upsert", event.dest_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, path: str) -> bool:
        """Check if the file resides inside an excluded directory.

        Inspects the parent directory segments (not the filename itself)
        to stay consistent with the indexer's os.walk filtering.
        """
        parent_parts = Path(path).parent.parts
        return any(
            part in EXCLUDED_DIRS or (part.startswith(".") and len(part) > 1)
            for part in parent_parts
        )

    def _schedule(self, action: str, path: str):
        """Debounce an event — wait DEBOUNCE_SECONDS before processing."""
        key = f"{action}:{path}"
        with self._lock:
            existing = self._pending.get(key)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(
                self.DEBOUNCE_SECONDS, self._execute, args=(action, path)
            )
            timer.daemon = True
            self._pending[key] = timer
            timer.start()

    def _execute(self, action: str, path: str):
        """Process a debounced file system event."""
        key = f"{action}:{path}"
        with self._lock:
            self._pending.pop(key, None)

        if action == "delete":
            delete_file_by_path(path)
            print(f"[Lithe Watcher] Removed: {os.path.basename(path)}")

        elif action == "upsert":
            try:
                stat = os.stat(path)
                _, ext = os.path.splitext(path)
                file_record = {
                    "path": path,
                    "name": os.path.basename(path),
                    "extension": ext.lower() if ext else "",
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                    "indexed_at": time.time(),
                    "category": categorize_path(path),
                }
                upsert_files([file_record])
                print(f"[Lithe Watcher] Indexed: {os.path.basename(path)}")
            except FileNotFoundError:
                pass  # File was deleted before we could stat it
            except Exception as e:
                print(f"[Lithe Watcher] Error processing {path}: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_watcher() -> Observer | None:
    """Start the file system watcher for all whitelisted directories.

    Schedules recursive watchers on each directory in INDEX_WHITELIST.
    The Observer runs as a daemon thread and stops automatically when
    the main process exits.

    Returns:
        The Observer instance (call .stop() to shut down),
        or None if there are no directories to watch.
    """
    if not INDEX_WHITELIST:
        print("[Lithe Watcher] INDEX_WHITELIST is empty. Nothing to watch.")
        return None

    observer = Observer()
    observer.daemon = True
    handler = _LitheEventHandler()

    watched = 0
    for directory in INDEX_WHITELIST:
        if os.path.isdir(directory):
            observer.schedule(handler, directory, recursive=True)
            print(f"[Lithe Watcher] Watching: {directory}")
            watched += 1
        else:
            print(f"[Lithe Watcher] Warning: Directory not found: {directory}")

    if watched == 0:
        print("[Lithe Watcher] No valid directories to watch.")
        return None

    observer.start()
    print(f"[Lithe Watcher] File system watcher started ({watched} directories).")
    return observer
