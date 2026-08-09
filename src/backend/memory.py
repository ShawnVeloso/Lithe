"""
Lithe — Memory Layer (F-03: Local Directory Indexer)

Initializes and manages the local SQLite database used to store file metadata.
This acts as Lithe's "Memory" of the local file system.

Phase 3 additions:
  - `category` column for heuristic tags (The Heuristic Graph)
  - `delete_file_by_path()` for the file watcher's delete events
  - Schema migration for existing databases
"""

import sqlite3
from typing import Any, Dict, List

from src.backend.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Returns a configured SQLite connection with WAL mode enabled.

    WAL (Write-Ahead Logging) allows simultaneous readers and a single
    writer without blocking — critical because the background indexer
    thread writes while the LLM reads concurrently.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db() -> None:
    """Initializes the database schema if it doesn't exist.

    Also runs migrations for existing databases (e.g., adding the
    `category` column introduced in Phase 3).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                extension TEXT,
                size_bytes INTEGER,
                modified_at REAL,
                indexed_at REAL,
                category TEXT DEFAULT ''
            )
            """
        )

        # --- Feature 3 (Tier 2): Undo Stack ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                details_json TEXT NOT NULL,
                reversible BOOLEAN NOT NULL DEFAULT 1,
                timestamp REAL NOT NULL
            )
            """
        )
        
        # --- Feature 4 (Tier 2): Persistent Chat History ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_proposal_json TEXT,
                tool_resolution TEXT,
                timestamp REAL NOT NULL
            )
            """
        )

        # --- Migration: add `category` column to existing databases ---
        existing_cols = [
            col[1] for col in cursor.execute("PRAGMA table_info(files)").fetchall()
        ]
        if "category" not in existing_cols:
            cursor.execute("ALTER TABLE files ADD COLUMN category TEXT DEFAULT ''")

        # Create an index on extension for faster filtering of research files
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)"
        )
        conn.commit()


def upsert_files(files: List[Dict[str, Any]]) -> None:
    """
    Inserts or updates file records in the database.
    
    Args:
        files: A list of dictionaries containing file metadata.
               Keys should match the table columns:
               path, name, extension, size_bytes, modified_at, indexed_at, category
    """
    if not files:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO files (path, name, extension, size_bytes, modified_at, indexed_at, category)
            VALUES (:path, :name, :extension, :size_bytes, :modified_at, :indexed_at, :category)
            ON CONFLICT(path) DO UPDATE SET
                name=excluded.name,
                extension=excluded.extension,
                size_bytes=excluded.size_bytes,
                modified_at=excluded.modified_at,
                indexed_at=excluded.indexed_at,
                category=excluded.category
            """,
            files,
        )
        conn.commit()


def delete_file_by_path(path: str) -> None:
    """Removes a file record from the database by its absolute path.

    Called by the file watcher when a file is deleted from the filesystem.
    No-op if the path doesn't exist in the database.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM files WHERE path = ?", (path,))
        conn.commit()


def delete_files_by_root_directory(root: str) -> None:
    """Removes all file records under a specific root directory.
    
    Used when a directory is removed from the whitelist.
    """
    normalized = root.replace("\\", "/")
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM files WHERE REPLACE(path, '\\', '/') LIKE ?",
            (f"{normalized}%",),
        )
        conn.commit()


def delete_files_by_paths(paths: List[str]) -> None:
    """Removes multiple file records by their absolute paths in batches.
    
    Used during startup reconciliation to clean up removed or excluded files.
    """
    if not paths:
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        # SQLite has a limit on variables in a query (usually 999), batch in 900
        for i in range(0, len(paths), 900):
            chunk = paths[i:i+900]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(f"DELETE FROM files WHERE path IN ({placeholders})", chunk)
        conn.commit()


def delete_files_by_extension(ext: str) -> None:
    """Removes all file records with a specific extension."""
    ext = ext.lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    with get_connection() as conn:
        conn.execute("DELETE FROM files WHERE extension = ?", (ext,))
        conn.commit()


def get_all_files_mtime() -> Dict[str, float]:
    """Fetches a dictionary mapping all indexed paths to their modified_at timestamp.
    
    Used by the indexer to reconcile the current state of the filesystem
    against the stored database without running slow os.stat calls on unchanged files.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT path, modified_at FROM files")
        return {row["path"]: row["modified_at"] for row in cursor.fetchall()}


def find_file_paths(filenames: List[str]) -> List[str]:
    """
    Finds the absolute paths for a list of filenames in the SQLite DB.
    Matches are case-insensitive.
    """
    if not filenames:
        return []

    # Use parameterized query to prevent SQL injection and handle quotes
    placeholders = ",".join(["?"] * len(filenames))
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT path FROM files WHERE name COLLATE NOCASE IN ({placeholders})",
            filenames
        )
        rows = cursor.fetchall()
        return [row["path"] for row in rows]


def search_files_by_name(keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Searches indexed files by keyword (fuzzy match on filename).
    Returns up to `limit` results with path, name, extension, size, and category.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT path, name, extension, size_bytes, category
            FROM files
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY modified_at DESC
            LIMIT ?
            """,
            (f"%{keyword}%", limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "path": row["path"],
                "name": row["name"],
                "extension": row["extension"],
                "size_bytes": row["size_bytes"],
                "category": row["category"] or "",
            }
            for row in rows
        ]


def get_file_count_by_directory(roots: List[str]) -> List[Dict[str, Any]]:
    """Returns the number of indexed files under each root directory.

    Used by the /api/status endpoint to feed the [01] INDEX HUD panel.

    Args:
        roots: List of whitelisted root directory paths.

    Returns:
        List of dicts with 'path' and 'file_count' keys.
    """
    results = []
    with get_connection() as conn:
        cursor = conn.cursor()
        for root in roots:
            # Normalize to forward slashes for consistent LIKE matching
            normalized = root.replace("\\", "/")
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM files WHERE REPLACE(path, '\\', '/') LIKE ?",
                (f"{normalized}%",),
            )
            row = cursor.fetchone()
            results.append({"path": root, "file_count": row["cnt"] if row else 0})
    return results

import time

def record_action(tool_name: str, details_json: str, reversible: bool = True) -> None:
    """Records an action in the undo stack."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO action_history (tool_name, details_json, reversible, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (tool_name, details_json, reversible, time.time())
        )
        conn.commit()

def get_action_history(limit: int = 5) -> List[Dict[str, Any]]:
    """Returns the most recent actions."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tool_name, details_json, reversible, timestamp
            FROM action_history
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_action_by_id(action_id: int) -> Dict[str, Any]:
    """Retrieves a specific action."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM action_history WHERE id = ?", (action_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def delete_action(action_id: int) -> None:
    """Removes an action from history (e.g. after undo)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM action_history WHERE id = ?", (action_id,))
        conn.commit()

# ---------------------------------------------------------------------------
# Feature 4: Persistent Chat History
# ---------------------------------------------------------------------------

def save_message(msg_id: str, role: str, content: str, tool_proposal_json: str = None, tool_resolution: str = None) -> None:
    """Saves a message to the chat history."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (id, role, content, tool_proposal_json, tool_resolution, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content=excluded.content,
                tool_proposal_json=excluded.tool_proposal_json,
                tool_resolution=excluded.tool_resolution
            """,
            (msg_id, role, content, tool_proposal_json, tool_resolution, time.time())
        )
        conn.commit()

def get_chat_history() -> List[Dict[str, Any]]:
    """Retrieves the full chat history ordered by timestamp."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, role, content, tool_proposal_json, tool_resolution, timestamp FROM messages ORDER BY timestamp ASC")
        return [dict(row) for row in cursor.fetchall()]

# Ensure DB is initialized when this module is imported
init_db()
