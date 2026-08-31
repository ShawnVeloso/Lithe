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

        # --- Feature 3 (Tier 2): Undo Stack + Audit Log ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                details_json TEXT NOT NULL,
                reversible BOOLEAN NOT NULL DEFAULT 1,
                timestamp REAL NOT NULL,
                decision_outcome TEXT DEFAULT '',
                execution_result TEXT DEFAULT '',
                conversation_id TEXT DEFAULT ''
            )
            """
        )
        
        # --- Feature 4 (Tier 2): Persistent Chat History ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_proposal_json TEXT,
                tool_resolution TEXT,
                timestamp REAL NOT NULL,
                is_auto_summary BOOLEAN DEFAULT 0
            )
            """
        )

        # --- Migration: add `category` column to existing databases ---
        existing_cols = [
            col[1] for col in cursor.execute("PRAGMA table_info(files)").fetchall()
        ]
        if "category" not in existing_cols:
            cursor.execute("ALTER TABLE files ADD COLUMN category TEXT DEFAULT ''")

        # --- Migration: add `conversation_id` column to existing databases ---
        existing_msg_cols = [
            col[1] for col in cursor.execute("PRAGMA table_info(messages)").fetchall()
        ]
        if "conversation_id" not in existing_msg_cols:
            cursor.execute("ALTER TABLE messages ADD COLUMN conversation_id TEXT DEFAULT 'default'")
        if "is_auto_summary" not in existing_msg_cols:
            cursor.execute("ALTER TABLE messages ADD COLUMN is_auto_summary BOOLEAN DEFAULT 0")

        # --- Migration: add audit columns to action_history ---
        existing_ah_cols = [
            col[1] for col in cursor.execute("PRAGMA table_info(action_history)").fetchall()
        ]
        if "decision_outcome" not in existing_ah_cols:
            cursor.execute("ALTER TABLE action_history ADD COLUMN decision_outcome TEXT DEFAULT ''")
            cursor.execute("ALTER TABLE action_history ADD COLUMN execution_result TEXT DEFAULT ''")
            cursor.execute("ALTER TABLE action_history ADD COLUMN conversation_id TEXT DEFAULT ''")

        # --- Persistent key/value app state (e.g. active conversation pointer) ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        # --- Watch-and-Summarize (Segment 1): Watch Rules ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                directory TEXT NOT NULL,
                pattern TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT 'summarize',
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_watch_rules_dir_active ON watch_rules(directory, active)"
        )

        # --- Watch-and-Summarize (Segment 2): Auto Summaries ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at REAL NOT NULL,
                delivered BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY(rule_id) REFERENCES watch_rules(id)
            )
            """
        )

        # --- Purge undeliverable auto-summaries ---
        # Legacy rows written before the watcher's test-artefact filter and the
        # error-string guard in summarize_file_for_watch_rule existed. Left with
        # delivered = 0 they are re-fetched as "pending" on every restart.
        # Each clause is anchored so it cannot match a legitimate summary:
        #   - the exact string the old failure path stored, not a substring
        #     (a real summary may well contain "failed to generate");
        #   - the "Error: " prefix every _ollama_chat failure string carries,
        #     anchored so a summary merely mentioning an error survives;
        #   - orphans, whose parent rule no longer exists — rules are only ever
        #     soft-deleted, so a real summary always has its watch_rules row.
        cursor.execute(
            """
            DELETE FROM auto_summaries
             WHERE delivered = 0
               AND (summary = 'Failed to generate summary.'
                 OR summary LIKE 'Error: %'
                 OR rule_id NOT IN (SELECT id FROM watch_rules))
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

def record_action(
    tool_name: str, 
    details_json: str, 
    reversible: bool = True,
    decision_outcome: str = "",
    execution_result: str = "",
    conversation_id: str = ""
) -> None:
    """Records an action in the undo stack / audit log."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO action_history (tool_name, details_json, reversible, timestamp, decision_outcome, execution_result, conversation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tool_name, details_json, reversible, time.time(), decision_outcome, execution_result, conversation_id)
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

def export_action_history(from_timestamp: float | None = None, to_timestamp: float | None = None) -> List[Dict[str, Any]]:
    """Returns all actions, optionally filtered by timestamp, for the Audit Log."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM action_history WHERE 1=1"
        params = []
        if from_timestamp is not None:
            query += " AND timestamp >= ?"
            params.append(from_timestamp)
        if to_timestamp is not None:
            query += " AND timestamp <= ?"
            params.append(to_timestamp)
        query += " ORDER BY timestamp ASC"
        
        cursor.execute(query, params)
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

def get_latest_conversation_id() -> str | None:
    """Returns the most recent conversation_id, or None if no messages exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT conversation_id FROM messages ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        return row["conversation_id"] if row else None

def save_message(msg_id: str, conversation_id: str, role: str, content: str, tool_proposal_json: str = None, tool_resolution: str = None, is_auto_summary: bool = False) -> None:
    """Saves a message to the chat history."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, tool_proposal_json, tool_resolution, timestamp, is_auto_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content=excluded.content,
                tool_proposal_json=excluded.tool_proposal_json,
                tool_resolution=excluded.tool_resolution
            """,
            (msg_id, conversation_id, role, content, tool_proposal_json, tool_resolution, time.time(), is_auto_summary)
        )
        conn.commit()

def get_chat_history(conversation_id: str) -> List[Dict[str, Any]]:
    """Retrieves the full chat history for a given conversation ordered by timestamp."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, role, content, tool_proposal_json, tool_resolution, timestamp, is_auto_summary FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC", (conversation_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_app_state(key: str) -> str | None:
    """Reads a persisted app-state value, or None if unset."""
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_app_state(key: str, value: str) -> None:
    """Persists an app-state value (upsert)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()

# ---------------------------------------------------------------------------
# Watch-and-Summarize: Watch Rules CRUD
# ---------------------------------------------------------------------------

def insert_watch_rule(directory: str, pattern: str, action: str = "summarize") -> int:
    """Inserts a new watch rule and returns the new row's id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO watch_rules (directory, pattern, action, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (directory, pattern, action, time.time())
        )
        conn.commit()
        return cursor.lastrowid


def get_active_watch_rules() -> List[Dict[str, Any]]:
    """Returns all watch rules where active = 1."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, directory, pattern, action, created_at FROM watch_rules WHERE active = 1 ORDER BY created_at ASC"
        )
        return [dict(row) for row in cursor.fetchall()]


def soft_delete_watch_rule(rule_id: int) -> bool:
    """Sets active = 0 for the given rule id. Returns True if the row existed."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE watch_rules SET active = 0 WHERE id = ? AND active = 1",
            (rule_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_watch_rule_by_id(rule_id: int) -> Dict[str, Any] | None:
    """Returns a single watch rule by id, or None if not found."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watch_rules WHERE id = ?", (rule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def insert_auto_summary(rule_id: int, file_path: str, summary: str) -> int:
    """Inserts a generated file summary into the auto_summaries table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO auto_summaries (rule_id, file_path, summary, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (rule_id, file_path, summary, time.time())
        )
        conn.commit()
        return cursor.lastrowid


# Ensure DB is initialized when this module is imported
init_db()

def get_pending_auto_summaries() -> List[Dict[str, Any]]:
    """Returns all auto summaries where delivered = 0."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM auto_summaries WHERE delivered = 0 ORDER BY created_at ASC")
        return [dict(row) for row in cursor.fetchall()]

def ack_auto_summaries(summary_ids: List[int], conversation_id: str = "system") -> None:
    """Marks auto summaries as delivered and inserts them into the messages table in a single transaction.

    ``conversation_id`` binds the delivered summary to the chat it appeared in so it
    reloads with that conversation on restart (and does not leak into new chats).
    """
    if not summary_ids:
        return

    conversation_id = conversation_id or "system"
    placeholders = ",".join("?" * len(summary_ids))

    with get_connection() as conn:
        cursor = conn.cursor()

        # Phase 1 — bury, and commit immediately. Burial must not share a
        # transaction with the chat binding below: when the two were atomic, any
        # failure while writing the message rolled the UPDATE back too, and the
        # summaries returned as pending on every restart.
        cursor.execute(
            f"UPDATE auto_summaries SET delivered = 1 WHERE id IN ({placeholders})",
            summary_ids,
        )
        conn.commit()

        # Phase 2 — bind each summary to the conversation it was shown in.
        for sid in summary_ids:
            cursor.execute("SELECT file_path, summary FROM auto_summaries WHERE id = ?", (sid,))
            row = cursor.fetchone()
            if not row:
                continue

            msg_id = f"auto-summary-{sid}"
            content = f"**[Watch Rule Auto-Summary]** {row['file_path']}\n\n{row['summary']}"

            cursor.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, timestamp, is_auto_summary)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (msg_id, conversation_id, 'assistant', content, time.time(), 1)
            )

        conn.commit()
