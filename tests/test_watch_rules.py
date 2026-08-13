"""
Tests for Watch-and-Summarize Segment 1: Rule Storage & Management

Covers:
  - create_watch_rule: valid directory, invalid directory rejection
  - list_watch_rules: empty, populated
  - delete_watch_rule: valid id, nonexistent id
  - Full create → list → delete → list cycle
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from src.backend import memory
from src.backend import watch_rules as wr


@pytest.fixture
def mock_env(tmp_path):
    """Provides a temp DB and a fake whitelist for isolated testing."""
    db_file = tmp_path / "test_watch_rules.db"
    fake_whitelist = [
        os.path.normpath("D:\\Downloads"),
        os.path.normpath("D:\\Projects"),
    ]

    with patch("src.backend.memory.DB_PATH", db_file), \
         patch("src.backend.watch_rules.INDEX_WHITELIST", fake_whitelist):
        memory.init_db()
        yield {
            "db_file": db_file,
            "whitelist": fake_whitelist,
        }


# -----------------------------------------------------------------------
# create_watch_rule
# -----------------------------------------------------------------------

def test_create_watch_rule_valid(mock_env):
    """Creating a rule for a whitelisted directory succeeds."""
    result = wr.create_watch_rule("D:\\Downloads", "*.pdf")
    assert "Watch rule #" in result
    assert "*.pdf" in result
    assert "Downloads" in result


def test_create_watch_rule_subdirectory(mock_env):
    """Creating a rule for a sub-directory of a whitelisted root succeeds."""
    result = wr.create_watch_rule("D:\\Downloads\\Reports", "*.csv")
    assert "Watch rule #" in result
    assert "*.csv" in result


def test_create_watch_rule_invalid_directory(mock_env):
    """Creating a rule for a non-whitelisted directory returns an error."""
    result = wr.create_watch_rule("C:\\Windows", "*.log")
    assert result.startswith("ERROR:")
    assert "not a currently watched directory" in result


def test_create_watch_rule_normalises_path(mock_env):
    """Forward slashes and trailing slashes are normalised before comparison."""
    # Use forward slashes + trailing slash — should still match D:\Downloads
    result = wr.create_watch_rule("D:/Downloads/", "*.pdf")
    assert "Watch rule #" in result


# -----------------------------------------------------------------------
# list_watch_rules
# -----------------------------------------------------------------------

def test_list_watch_rules_empty(mock_env):
    """Listing when no rules exist returns a readable empty message."""
    result = wr.list_watch_rules()
    assert result == "No active watch rules."


def test_list_watch_rules_populated(mock_env):
    """Listing after creating rules shows all of them."""
    wr.create_watch_rule("D:\\Downloads", "*.pdf")
    wr.create_watch_rule("D:\\Projects", "*.py")

    result = wr.list_watch_rules()
    assert "*.pdf" in result
    assert "*.py" in result
    assert "Active watch rules (2)" in result


# -----------------------------------------------------------------------
# delete_watch_rule
# -----------------------------------------------------------------------

def test_delete_watch_rule_valid(mock_env):
    """Deleting an existing rule succeeds and removes it from the active list."""
    wr.create_watch_rule("D:\\Downloads", "*.pdf")
    rules = memory.get_active_watch_rules()
    assert len(rules) == 1
    rule_id = rules[0]["id"]

    result = wr.delete_watch_rule(rule_id)
    assert f"#{rule_id} deleted" in result

    # Should no longer appear in active list
    assert memory.get_active_watch_rules() == []


def test_delete_watch_rule_nonexistent(mock_env):
    """Deleting a nonexistent rule returns a clear error."""
    result = wr.delete_watch_rule(99999)
    assert result.startswith("ERROR:")
    assert "99999" in result


def test_delete_watch_rule_soft_delete(mock_env):
    """Soft-deleted rules are still in the DB with active=0."""
    wr.create_watch_rule("D:\\Downloads", "*.pdf")
    rules = memory.get_active_watch_rules()
    rule_id = rules[0]["id"]

    wr.delete_watch_rule(rule_id)

    # Active list is empty
    assert memory.get_active_watch_rules() == []

    # But the row still exists in the DB
    row = memory.get_watch_rule_by_id(rule_id)
    assert row is not None
    assert row["active"] == 0


def test_delete_watch_rule_invalid_id_type(mock_env):
    """Passing a non-numeric id returns a clear error."""
    result = wr.delete_watch_rule("not_a_number")
    assert result.startswith("ERROR:")
    assert "Invalid rule ID" in result


# -----------------------------------------------------------------------
# Full cycle integration
# -----------------------------------------------------------------------

def test_full_create_list_delete_cycle(mock_env):
    """End-to-end: create → list → verify → delete → list empty."""
    # Create
    create_result = wr.create_watch_rule("D:\\Downloads", "*.pdf")
    assert "Watch rule #" in create_result

    # List — should show 1 rule
    list_result = wr.list_watch_rules()
    assert "*.pdf" in list_result
    assert "Active watch rules (1)" in list_result

    # Extract the rule ID from the DB directly
    rules = memory.get_active_watch_rules()
    assert len(rules) == 1
    rule_id = rules[0]["id"]

    # Delete
    delete_result = wr.delete_watch_rule(rule_id)
    assert "deleted" in delete_result

    # List — should be empty now
    list_empty = wr.list_watch_rules()
    assert list_empty == "No active watch rules."
