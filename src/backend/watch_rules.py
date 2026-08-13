"""
Lithe — Watch Rules Tools (Tier 3, Segment 1)

LLM-callable functions for managing watch rules.
Watch rules define per-directory glob patterns that the watcher will act on
(e.g., "summarize every new *.pdf in Downloads").

These tools are read/write to the app's own SQLite database only — they
never touch user files on disk, so they auto-execute without ToolProposalCard.
"""

import os
import json
import time
from datetime import datetime, timezone

from src.backend.config import INDEX_WHITELIST
from src.backend.memory import (
    insert_watch_rule,
    get_active_watch_rules,
    soft_delete_watch_rule,
    record_action,
)


def _is_watched_directory(directory: str) -> bool:
    """Check if a directory is in the current INDEX_WHITELIST.

    Normalises both sides (forward-slash, lowered, trailing-slash stripped)
    so that ``D:\\Downloads`` matches ``d:/downloads`` in the whitelist.
    """
    norm = os.path.normpath(directory).lower()
    for w in INDEX_WHITELIST:
        if os.path.normpath(w).lower() == norm:
            return True
        # Also allow sub-directories of whitelisted roots
        if norm.startswith(os.path.normpath(w).lower() + os.sep):
            return True
    return False


def create_watch_rule(directory: str, pattern: str, conversation_id: str = "") -> str:
    """Creates a watch rule for a directory.

    The directory must already be whitelisted (present in INDEX_WHITELIST).
    The pattern is a simple glob (e.g. ``*.pdf``).
    The only supported action today is ``summarize``.

    Args:
        directory: An absolute directory path that is currently watched/whitelisted.
        pattern:   A file glob pattern (e.g. ``*.pdf``, ``report_*.csv``).
        conversation_id: Internal — injected by brain.py for audit logging.

    Returns:
        A confirmation string with the new rule's id, or an error message.
    """
    print(f"[TOOL EXECUTED] create_watch_rule: {pattern} in {directory}")

    # Normalise the directory path for consistency
    directory = os.path.normpath(directory)

    if not _is_watched_directory(directory):
        err = (
            f"ERROR: '{directory}' is not a currently watched directory. "
            f"Watched directories: {', '.join(INDEX_WHITELIST) if INDEX_WHITELIST else '(none)'}. "
            f"Add the directory to the whitelist first."
        )
        record_action(
            "create_watch_rule",
            json.dumps({"directory": directory, "pattern": pattern}),
            reversible=False,
            decision_outcome="auto-executed",
            execution_result="failed (directory not watched)",
            conversation_id=conversation_id,
        )
        return err

    rule_id = insert_watch_rule(directory, pattern, action="summarize")

    record_action(
        "create_watch_rule",
        json.dumps({"rule_id": rule_id, "directory": directory, "pattern": pattern, "action": "summarize"}),
        reversible=False,
        decision_outcome="auto-executed",
        execution_result="success",
        conversation_id=conversation_id,
    )

    return f"Watch rule #{rule_id} created: {pattern} in {directory} (action: summarize)"


def list_watch_rules(conversation_id: str = "") -> str:
    """Lists all active watch rules.

    Args:
        conversation_id: Internal — injected by brain.py for audit logging.

    Returns:
        A formatted text listing of all active rules, or a message if none exist.
    """
    print("[TOOL EXECUTED] list_watch_rules")

    rules = get_active_watch_rules()
    if not rules:
        return "No active watch rules."

    lines = [f"Active watch rules ({len(rules)}):"]
    lines.append(f"  {'ID':<6} {'Directory':<40} {'Pattern':<16} {'Created'}")
    lines.append(f"  {'—'*6} {'—'*40} {'—'*16} {'—'*20}")
    for r in rules:
        created = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"  {r['id']:<6} {r['directory']:<40} {r['pattern']:<16} {created}"
        )
    return "\n".join(lines)


def delete_watch_rule(rule_id: int, conversation_id: str = "") -> str:
    """Deletes (deactivates) a watch rule by its ID.

    Uses soft delete — the row stays in the database with ``active = 0``
    for audit purposes.

    Args:
        rule_id: The numeric ID of the rule to delete.
        conversation_id: Internal — injected by brain.py for audit logging.

    Returns:
        A confirmation string, or an error if the id doesn't exist.
    """
    print(f"[TOOL EXECUTED] delete_watch_rule: #{rule_id}")

    # Coerce to int in case the LLM sends a string
    try:
        rule_id = int(rule_id)
    except (ValueError, TypeError):
        return f"ERROR: Invalid rule ID '{rule_id}'. Must be a number."

    success = soft_delete_watch_rule(rule_id)

    if not success:
        record_action(
            "delete_watch_rule",
            json.dumps({"rule_id": rule_id}),
            reversible=False,
            decision_outcome="auto-executed",
            execution_result="failed (not found)",
            conversation_id=conversation_id,
        )
        return f"ERROR: No active watch rule with id {rule_id} found."

    record_action(
        "delete_watch_rule",
        json.dumps({"rule_id": rule_id}),
        reversible=False,
        decision_outcome="auto-executed",
        execution_result="success",
        conversation_id=conversation_id,
    )
    return f"Watch rule #{rule_id} deleted."
