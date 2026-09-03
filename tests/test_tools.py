import os
import pytest
from src.backend.tools import (
    execute_rename,
    execute_delete,
    execute_write,
    execute_read,
    MAX_READ_BYTES,
)

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


# ---------------------------------------------------------------------------
# execute_read — the companion to search_files, which matches filenames only
# ---------------------------------------------------------------------------

def test_execute_read_returns_file_contents(isolated_db, tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("the code word is ZEPHYR-441", encoding="utf-8")
    assert "ZEPHYR-441" in execute_read(str(target))


def test_execute_read_truncates_with_an_explicit_marker(isolated_db, tmp_path):
    """The model must be told it is seeing a fragment, or it will answer as if
    it had read the whole file."""
    target = tmp_path / "big.txt"
    target.write_text("x" * (MAX_READ_BYTES * 2), encoding="utf-8")

    result = execute_read(str(target))
    assert result.startswith("[TRUNCATED:")
    assert len(result) < MAX_READ_BYTES * 2


def test_execute_read_rejects_binary_rather_than_guessing(isolated_db, tmp_path):
    target = tmp_path / "logo.png"
    target.write_bytes(bytes([0x89]) + b"PNG" + bytes([0x0d, 0x0a, 0x1a, 0x0a, 0xff, 0xfe]))
    assert "ERROR" in execute_read(str(target))


def test_execute_read_reports_a_missing_file(isolated_db, tmp_path):
    assert "not found" in execute_read(str(tmp_path / "nope.txt")).lower()


def test_execute_read_refuses_protected_system_paths(isolated_db):
    """Reads go through the same path guard as the mutating tools."""
    result = execute_read(r"C:\Windows\System32\config\SAM")
    assert "protected system path" in result.lower()
