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

from src.backend.heuristics import categorize_path

# Module-level state
last_event_time: float | None = None
_observer: Observer | None = None
_handler = None
_watches = {}


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
        global last_event_time
        last_event_time = time.time()
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
    """Start the file system watcher for all whitelisted directories."""
    global _observer, _handler
    if _observer is not None:
        return _observer

    _observer = Observer()
    _observer.daemon = True
    _handler = _LitheEventHandler()

    for directory in INDEX_WHITELIST:
        add_watch(directory)

    if not _watches:
        print("[Lithe Watcher] No valid directories to watch.")
        # We start the observer anyway so we can add watches later
        _observer.start()
        return _observer

    _observer.start()
    print(f"[Lithe Watcher] File system watcher started ({len(_watches)} directories).")
    return _observer


def add_watch(path: str) -> bool:
    """Dynamically add a directory to the active watcher."""
    global _observer, _handler, _watches
    if not _observer or not _handler:
        return False
    if path in _watches:
        return True
    if os.path.isdir(path):
        watch = _observer.schedule(_handler, path, recursive=True)
        _watches[path] = watch
        print(f"[Lithe Watcher] Started watching: {path}")
        return True
    else:
        print(f"[Lithe Watcher] Warning: Directory not found: {path}")
        return False


def remove_watch(path: str) -> None:
    """Dynamically remove a directory from the active watcher."""
    global _observer, _watches
    if not _observer:
        return
    watch = _watches.pop(path, None)
    if watch:
        _observer.unschedule(watch)
        print(f"[Lithe Watcher] Stopped watching: {path}")
