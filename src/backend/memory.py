"""
Lithe — Memory Layer (F-03: Local Directory Indexer)

Initializes and manages the local SQLite database used to store file metadata.
This acts as Lithe's "Memory" of the local file system.
"""

import sqlite3
from typing import Any, Dict, List

from src.backend.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Returns a configured SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes the database schema if it doesn't exist."""
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
                indexed_at REAL
            )
            """
        )
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
               path, name, extension, size_bytes, modified_at, indexed_at
    """
    if not files:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO files (path, name, extension, size_bytes, modified_at, indexed_at)
            VALUES (:path, :name, :extension, :size_bytes, :modified_at, :indexed_at)
            ON CONFLICT(path) DO UPDATE SET
                name=excluded.name,
                extension=excluded.extension,
                size_bytes=excluded.size_bytes,
                modified_at=excluded.modified_at,
                indexed_at=excluded.indexed_at
            """,
            files,
        )
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

# Ensure DB is initialized when this module is imported
init_db()
