import os
import pytest
from src.backend.tools import execute_rename, execute_delete, execute_write

def test_execute_rename_safeword_missing(tmp_path):
    """Test rename with safeword active = False."""
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "dst.txt"
    
    result = execute_rename(str(src), str(dst), safeword_active=False)
    assert "ERROR: User permission required" in result
    assert not dst.exists()

def test_execute_rename_success(tmp_path):
    """Test rename with safeword active = True."""
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "dst.txt"
    
    result = execute_rename(str(src), str(dst), safeword_active=True)
    assert "SUCCESS" in result
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "hello"

def test_execute_delete_safeword_missing(tmp_path):
    """Test delete with safeword active = False."""
    target = tmp_path / "del.txt"
    target.write_text("hello")
    
    result = execute_delete(str(target), safeword_active=False)
    assert "ERROR: User permission required" in result
    assert target.exists()

def test_execute_delete_success(tmp_path):
    """Test delete with safeword active = True."""
    target = tmp_path / "del.txt"
    target.write_text("hello")
    
    result = execute_delete(str(target), safeword_active=True)
    assert "SUCCESS" in result
    assert not target.exists()

def test_execute_write_safeword_missing(tmp_path):
    """Test write with safeword active = False."""
    target = tmp_path / "write.txt"
    
    result = execute_write(str(target), "hello", mode="overwrite", safeword_active=False)
    assert "ERROR: User permission required" in result
    assert not target.exists()

def test_execute_write_success(tmp_path):
    """Test write with safeword active = True."""
    target = tmp_path / "write.txt"
    
    result = execute_write(str(target), "hello", mode="overwrite", safeword_active=True)
    assert "SUCCESS" in result
    assert target.exists()
    assert target.read_text() == "hello"

def test_path_validation_protected_paths():
    """Test path validation against protected paths."""
    # Assuming C:\Windows is protected
    result = execute_delete(r"C:\Windows\System32\cmd.exe", safeword_active=True)
    assert "Refusing to modify protected system path" in result
