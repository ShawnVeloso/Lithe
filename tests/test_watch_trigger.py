import os
import time
from unittest.mock import patch, MagicMock

import pytest

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr("src.backend.config.DB_PATH", str(db_path))
    monkeypatch.setattr("src.backend.memory.DB_PATH", str(db_path))
    from src.backend import memory
    memory.init_db()
    
    yield db_path
    
    # Cleanup to avoid locked DB issues across tests
    try:
        os.remove(str(db_path))
    except Exception:
        pass

def test_watch_trigger_rule_matching(isolated_db):
    """Confirm rule matching logic in watcher's _execute('create') dispatch."""
    from src.backend.memory import insert_watch_rule
    from src.backend.watcher import _LitheEventHandler
    import os
    
    rule_dir = os.path.normcase(os.path.realpath("D:\\testdir"))
    rule_id = insert_watch_rule(rule_dir, "*.txt", "summarize")
    
    handler = _LitheEventHandler()
    
    with patch("src.backend.watcher.threading.Thread") as mock_thread, \
         patch("src.backend.watcher.upsert_files"), \
         patch("src.backend.watcher.os.stat") as mock_stat:
        
        mock_stat.return_value.st_size = 100
        mock_stat.return_value.st_mtime = time.time()
        
        # Test 1: Matching file (creation event)
        test_path = os.path.join(rule_dir, "hello.txt")
        handler._execute("create", test_path)
        
        assert mock_thread.called
        args, kwargs = mock_thread.call_args
        assert kwargs["target"].__name__ == "_run_with_timeout"
        assert kwargs["args"][1] == test_path
        assert kwargs["args"][2] == rule_id
        mock_thread.reset_mock()
        
        # Test 2: Non-matching extension
        handler._execute("create", os.path.join(rule_dir, "hello.md"))
        assert not mock_thread.called
        
        # Test 3: Modify event (should not trigger summary)
        handler._execute("upsert", test_path)
        assert not mock_thread.called

def test_summarize_file_for_watch_rule(isolated_db, tmp_path):
    """Confirm summary generation and DB insertion."""
    from src.backend.brain import summarize_file_for_watch_rule
    from src.backend.memory import get_connection
    
    test_file = tmp_path / "hello.txt"
    test_file.write_text("This is a test document.", encoding="utf-8")
    
    with patch("src.backend.brain._client") as mock_client:
        mock_response = MagicMock()
        mock_response.text = "Mock summary."
        mock_client.models.generate_content.return_value = mock_response
        
        summary = summarize_file_for_watch_rule(str(test_file), rule_id=99)
        assert summary == "Mock summary."
        
        # Verify DB insertion
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT summary, delivered FROM auto_summaries WHERE rule_id = 99")
            row = c.fetchone()
            assert row is not None
            assert row["summary"] == "Mock summary."
            assert row["delivered"] == 0

def test_summarize_file_for_watch_rule_unsupported_binary(isolated_db, tmp_path):
    """Confirm binary files are skipped gracefully."""
    from src.backend.brain import summarize_file_for_watch_rule
    
    # Create a dummy binary file
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"\x00\x01\x02\x03\xFF")
    
    # Should not even call LLM
    with patch("src.backend.brain._client") as mock_client:
        summary = summarize_file_for_watch_rule(str(test_file), rule_id=99)
        assert "Skipped (Binary or Unsupported)" in summary
        assert not mock_client.models.generate_content.called

def test_active_rule_filtering(isolated_db):
    """Confirm active=0 rules do not trigger."""
    from src.backend.memory import insert_watch_rule, get_connection
    from src.backend.watcher import _LitheEventHandler
    import os
    
    rule_dir = os.path.normcase(os.path.realpath("D:\\testdir"))
    rule_id = insert_watch_rule(rule_dir, "*.txt", "summarize")
    
    # Soft delete the rule
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE watch_rules SET active = 0 WHERE id = ?", (rule_id,))
        conn.commit()
        
    handler = _LitheEventHandler()
    
    with patch("src.backend.watcher.threading.Thread") as mock_thread, \
         patch("src.backend.watcher.upsert_files"), \
         patch("src.backend.watcher.os.stat") as mock_stat:
        
        mock_stat.return_value.st_size = 100
        mock_stat.return_value.st_mtime = time.time()
import os
import time
from unittest.mock import patch, MagicMock

import pytest

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr("src.backend.config.DB_PATH", str(db_path))
    monkeypatch.setattr("src.backend.memory.DB_PATH", str(db_path))
    from src.backend import memory
    memory.init_db()
    
    yield db_path
    
    # Cleanup to avoid locked DB issues across tests
    try:
        os.remove(str(db_path))
    except Exception:
        pass

def test_watch_trigger_rule_matching(isolated_db):
    """Confirm rule matching logic in watcher's _execute('create') dispatch."""
    from src.backend.memory import insert_watch_rule
    from src.backend.watcher import _LitheEventHandler
    import os
    
    rule_dir = os.path.normcase(os.path.realpath("D:\\testdir"))
    rule_id = insert_watch_rule(rule_dir, "*.txt", "summarize")
    
    handler = _LitheEventHandler()
    
    with patch("src.backend.watcher.threading.Thread") as mock_thread, \
         patch("src.backend.watcher.upsert_files"), \
         patch("src.backend.watcher.os.stat") as mock_stat:
        
        mock_stat.return_value.st_size = 100
        mock_stat.return_value.st_mtime = time.time()
        
        # Test 1: Matching file (creation event)
        test_path = os.path.join(rule_dir, "hello.txt")
        handler._execute("create", test_path)
        
        assert mock_thread.called
        args, kwargs = mock_thread.call_args
        assert kwargs["target"].__name__ == "_run_with_timeout"
        assert kwargs["args"][1] == test_path
        assert kwargs["args"][2] == rule_id
        mock_thread.reset_mock()
        
        # Test 2: Non-matching extension
        handler._execute("create", os.path.join(rule_dir, "hello.md"))
        assert not mock_thread.called
        
        # Test 3: Modify event (should not trigger summary)
        handler._execute("upsert", test_path)
        assert not mock_thread.called

def test_summarize_file_for_watch_rule(isolated_db, tmp_path):
    """Confirm summary generation and DB insertion."""
    from src.backend.brain import summarize_file_for_watch_rule
    from src.backend.memory import get_connection
    
    test_file = tmp_path / "hello.txt"
    test_file.write_text("This is a test document.", encoding="utf-8")
    
    with patch("src.backend.brain._client") as mock_client:
        mock_response = MagicMock()
        mock_response.text = "Mock summary."
        mock_client.models.generate_content.return_value = mock_response
        
        summary = summarize_file_for_watch_rule(str(test_file), rule_id=99)
        assert summary == "Mock summary."
        
        # Verify DB insertion
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT summary, delivered FROM auto_summaries WHERE rule_id = 99")
            row = c.fetchone()
            assert row is not None
            assert row["summary"] == "Mock summary."
            assert row["delivered"] == 0

def test_summarize_file_for_watch_rule_unsupported_binary(isolated_db, tmp_path):
    """Confirm binary files are skipped gracefully."""
    from src.backend.brain import summarize_file_for_watch_rule
    
    # Create a dummy binary file
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"\x00\x01\x02\x03\xFF")
    
    # Should not even call LLM
    with patch("src.backend.brain._client") as mock_client:
        summary = summarize_file_for_watch_rule(str(test_file), rule_id=99)
        assert "Skipped (Binary or Unsupported)" in summary
        assert not mock_client.models.generate_content.called

def test_active_rule_filtering(isolated_db):
    """Confirm active=0 rules do not trigger."""
    from src.backend.memory import insert_watch_rule, get_connection
    from src.backend.watcher import _LitheEventHandler
    import os
    
    rule_dir = os.path.normcase(os.path.realpath("D:\\testdir"))
    rule_id = insert_watch_rule(rule_dir, "*.txt", "summarize")
    
    # Soft delete the rule
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE watch_rules SET active = 0 WHERE id = ?", (rule_id,))
        conn.commit()
        
    handler = _LitheEventHandler()
    
    with patch("src.backend.watcher.threading.Thread") as mock_thread, \
         patch("src.backend.watcher.upsert_files"), \
         patch("src.backend.watcher.os.stat") as mock_stat:
        
        mock_stat.return_value.st_size = 100
        mock_stat.return_value.st_mtime = time.time()
        
        test_path = os.path.join(rule_dir, "hello.txt")
        handler._execute("create", test_path)
        
        assert not mock_thread.called, "Inactive rule should not have triggered dispatch"

def test_summarize_file_for_watch_rule_failure_handling(isolated_db, tmp_path):
    """Confirm summary generation failure does not insert into auto_summaries."""
    from src.backend.brain import summarize_file_for_watch_rule
    from src.backend.memory import get_connection
    
    test_file = tmp_path / "hello.txt"
    test_file.write_text("This is a test document.", encoding="utf-8")
    
    with patch("src.backend.brain._client") as mock_client:
        # Mock Gemini failure
        mock_client.models.generate_content.side_effect = Exception("Gemini API Error")
        
        with patch("src.backend.brain._ollama_chat") as mock_ollama:
            # Mock Ollama fallback failure (returns empty string)
            mock_ollama.return_value = ""
            
            summary = summarize_file_for_watch_rule(str(test_file), rule_id=99)
            
            assert summary == "Failed to generate summary."
            
            # Verify DB insertion (auto_summaries) is empty
            with get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM auto_summaries WHERE rule_id = 99")
                row = c.fetchone()
                assert row is None, "Should not insert into auto_summaries on failure"
                
                # Verify action_history logged the error
                c.execute("SELECT * FROM action_history WHERE tool_name = 'watch_rule_summary' ORDER BY id DESC LIMIT 1")
                err_row = c.fetchone()
                assert err_row is not None, "Should log to action_history on failure"
                assert "error: Failed to generate summary" in err_row["execution_result"]

def test_pending_and_ack_endpoints(isolated_db, tmp_path):
    """Confirm pending summaries can be fetched and acked."""
    from src.backend.memory import insert_watch_rule, insert_auto_summary, get_connection
    import time
    import os
    
    rule_dir = str(tmp_path)
    rule_id = insert_watch_rule(rule_dir, "*.txt", "summarize")
    
    # Insert two summaries
    sid1 = insert_auto_summary(rule_id, os.path.join(rule_dir, "file1.txt"), "Summary 1")
    sid2 = insert_auto_summary(rule_id, os.path.join(rule_dir, "file2.txt"), "Summary 2")
    
    # Test GET /api/watch-summaries/pending via memory function directly
    from src.backend.memory import get_pending_auto_summaries, ack_auto_summaries, get_chat_history
    
    pending = get_pending_auto_summaries()
    assert len(pending) == 2
    assert pending[0]["id"] == sid1
    assert pending[1]["id"] == sid2
    
    # Test ACK
    ack_auto_summaries([sid1])
    
    pending_after_ack = get_pending_auto_summaries()
    assert len(pending_after_ack) == 1
    assert pending_after_ack[0]["id"] == sid2
    
    # Verify sid1 is now in chat history under 'system'
    history = get_chat_history('system')
    assert len(history) == 1
    assert history[0]["id"] == f"auto-summary-{sid1}"
    assert history[0]["is_auto_summary"] == 1
    assert "Summary 1" in history[0]["content"]
