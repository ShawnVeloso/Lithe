import os
from fastapi.testclient import TestClient
from src.backend.server import app
import src.backend.memory as memory

def test_export_endpoints(tmp_path, monkeypatch):
    """Test the audit export endpoints with format and date filtering."""
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr("src.backend.memory.DB_PATH", str(db_path))
    
    # Initialize a clean database
    memory.init_db()
    
    # Add some dummy actions to history
    memory.record_action("write", '{"path": "/test1"}', True, decision_outcome="accepted")
    memory.record_action("delete", '{"path": "/test2"}', False, decision_outcome="rejected")

    client = TestClient(app)

    # Test JSON export
    res = client.get("/api/audit/export?format=json")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["tool_name"] == "write"

    # Test CSV export
    res = client.get("/api/audit/export?format=csv")
    assert res.status_code == 200
    assert "id,tool_name" in res.text
    assert "write" in res.text
    assert "delete" in res.text

    # Test Date filters
    res = client.get("/api/audit/export?format=json&from=2020-01-01T00:00:00Z&to=2030-01-01T00:00:00Z")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2

