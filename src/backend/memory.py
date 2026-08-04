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


# Ensure DB is initialized when this module is imported
init_db()
