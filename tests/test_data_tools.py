import os
import pandas as pd
from src.backend.data_tools import profile_data
from src.backend.memory import init_db, upsert_files

def test_profile_data(tmp_path, monkeypatch):
    # Setup test DB
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr("src.backend.config.DB_PATH", str(db_path))
    init_db()
    
    # Create test CSV
    csv_path = tmp_path / "test_data.csv"
    df = pd.DataFrame({
        "A": [1, 2, 3, None, 5],
        "B": ["a", "b", "c", "d", "e"]
    })
    df.to_csv(csv_path, index=False)
    
    # Insert file record into memory so find_file_paths works
    upsert_files([{
        "path": str(csv_path),
        "name": "test_data.csv",
        "extension": ".csv",
        "size_bytes": os.path.getsize(csv_path),
        "modified_at": os.path.getmtime(csv_path),
        "indexed_at": os.path.getmtime(csv_path),
        "category": "Data / Datasets"
    }])
    
    # Test profile_data
    result = profile_data("test_data.csv", conversation_id="test-conv")
    
    # Assertions
    assert "Total rows (analyzed): 5" in result
    assert "Total columns: 2" in result
    assert "A: float64 (Nulls: 1)" in result
    assert "B: object (Nulls: 0)" in result or "B: str (Nulls: 0)" in result
    assert "Summary Statistics (Numeric Columns)" in result
    
    # Test invalid extension
    txt_path = tmp_path / "test_data.txt"
    txt_path.write_text("dummy")
    upsert_files([{
        "path": str(txt_path),
        "name": "test_data.txt",
        "extension": ".txt",
        "size_bytes": 5,
        "modified_at": os.path.getmtime(txt_path),
        "indexed_at": os.path.getmtime(txt_path),
        "category": "Docs"
    }])
    result_invalid = profile_data("test_data.txt")
    assert "Unsupported file type" in result_invalid
