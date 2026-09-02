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

def test_get_conversations(mock_db_path):
    """Conversations are newest-first and titled by their FIRST user message."""
    # Fixed clock so the ordering assertion can't flake on timestamp ties.
    with patch("src.backend.memory.time.time", side_effect=[100.0, 200.0, 300.0, 400.0]):
        memory.save_message("a1", "conv-old", "user", "first question")
        memory.save_message("a2", "conv-old", "assistant", "an answer")
        memory.save_message("b1", "conv-new", "user", "newer question")
        memory.save_message("c1", "conv-bot", "assistant", "auto summary only")

    convs = memory.get_conversations()
    by_id = {c["conversation_id"]: c for c in convs}

    assert [c["conversation_id"] for c in convs] == ["conv-bot", "conv-new", "conv-old"]
    assert by_id["conv-old"]["title"] == "first question"  # first user msg, not "an answer"
    assert by_id["conv-bot"]["title"] is None              # no user message at all
    assert by_id["conv-old"]["last_at"] == 200.0           # latest msg, not the first

def test_delete_conversation_endpoint_rebinds_when_active(tmp_path, monkeypatch):
    """Deleting a conversation removes only its rows, and deleting the ACTIVE one
    leaves the backend bound to a fresh id rather than a ghost."""
    from fastapi.testclient import TestClient
    from src.backend.server import app
    import src.backend.brain as brain

    monkeypatch.setattr("src.backend.memory.DB_PATH", str(tmp_path / "test_memory.db"))
    memory.init_db()

    memory.save_message("k1", "keep-me", "user", "survivor")
    memory.save_message("d1", "kill-me", "user", "doomed")
    memory.record_action("write", '{"path": "/x"}', True, conversation_id="kill-me")
    memory.record_action("write", '{"path": "/y"}', True, conversation_id="keep-me")

    client = TestClient(app)

    # 1. Deleting a non-active conversation touches nothing else.
    monkeypatch.setattr(brain, "_current_conversation_id", "keep-me")
    res = client.delete("/api/chat/conversations/kill-me").json()
    assert res["was_active"] is False
    assert [c["conversation_id"] for c in memory.get_conversations()] == ["keep-me"]
    assert [a["conversation_id"] for a in memory.export_action_history()] == ["keep-me"]
    assert brain._current_conversation_id == "keep-me"

    # 2. Deleting the ACTIVE conversation rebinds to a new, different id.
    res = client.delete("/api/chat/conversations/keep-me").json()
    assert res["was_active"] is True
    assert res["conversation_id"] not in ("keep-me", "kill-me")
    assert brain._current_conversation_id == res["conversation_id"]
    assert memory.get_conversations() == []

def test_llm_config_endpoints(tmp_path, monkeypatch):
    """GET masks the key; POST persists to .env and applies live without a restart."""
    from fastapi.testclient import TestClient
    from src.backend.server import app
    from src.backend import config
    import src.backend.brain as brain

    env_file = tmp_path / ".env"
    env_file.write_text("OLLAMA_MODEL=old-model\n", encoding="utf-8")
    monkeypatch.setattr(config, "_ACTIVE_ENV_PATH", env_file)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "AIzaSyTESTKEY1234")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "old-model")
    monkeypatch.setattr(config, "OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setattr(config, "NEEDS_ONBOARDING", False)
    monkeypatch.setattr(brain, "OLLAMA_MODEL", "old-model")
    monkeypatch.setattr(brain, "OLLAMA_URL", "http://localhost:11434")

    client = TestClient(app)

    got = client.get("/api/config/llm").json()
    assert got["gemini_api_key_masked"] == "AIza...1234"
    assert "AIzaSyTESTKEY1234" not in str(got)   # the full key never leaves the backend

    res = client.post("/api/config/llm", json={"ollama_model": "llama3.2"}).json()
    assert res["ollama_model"] == "llama3.2"
    assert config.OLLAMA_MODEL == "llama3.2"     # in-memory, no restart
    assert brain.OLLAMA_MODEL == "llama3.2"      # brain's import-time copy rebound too
    assert "llama3.2" in env_file.read_text()    # persisted
    assert config.GEMINI_API_KEY == "AIzaSyTESTKEY1234"  # blank field == leave unchanged
