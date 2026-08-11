import os
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from src.backend import memory

@pytest.fixture
def mock_db_path(tmp_path):
    """Fixture to provide a temporary database path."""
    db_file = tmp_path / "test_memory.db"
    
    with patch("src.backend.memory.DB_PATH", db_file):
        memory.init_db()
        yield db_file

def test_init_db(mock_db_path):
    """Test that database initializes correctly."""
    conn = sqlite3.connect(mock_db_path)
    cursor = conn.cursor()
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    assert "files" in tables
    assert "action_history" in tables
    assert "messages" in tables
    conn.close()

def test_upsert_and_search_files(mock_db_path):
    """Test upserting files and searching them."""
    files = [
        {
            "path": "/test/file1.txt",
            "name": "file1.txt",
            "extension": ".txt",
            "size_bytes": 100,
            "modified_at": 1000.0,
            "indexed_at": 1001.0,
            "category": "doc"
        }
    ]
    memory.upsert_files(files)
    
    results = memory.search_files_by_name("file1")
    assert len(results) == 1
    assert results[0]["name"] == "file1.txt"

def test_save_and_get_chat_history(mock_db_path):
    """Test saving and retrieving chat history."""
    memory.save_message("msg1", "default", "user", "hello")
    memory.save_message("msg2", "default", "assistant", "world", '{"name": "tool"}', '{"status": "ok"}')
    
    history = memory.get_chat_history("default")
    assert len(history) == 2
    assert history[0]["id"] == "msg1"
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"
    
    assert history[1]["id"] == "msg2"
    assert history[1]["tool_proposal_json"] == '{"name": "tool"}'
    assert history[1]["tool_resolution"] == '{"status": "ok"}'

def test_action_history(mock_db_path):
    """Test action history for undo feature."""
    memory.record_action("write", '{"path": "/test"}', True)
    
    history = memory.get_action_history()
    assert len(history) == 1
    action_id = history[0]["id"]
    assert history[0]["tool_name"] == "write"
    
    memory.delete_action(action_id)
    history2 = memory.get_action_history()
    assert len(history2) == 0
