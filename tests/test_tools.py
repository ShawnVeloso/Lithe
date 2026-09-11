import os
import pytest
from src.backend.tools import (
    execute_rename,
    execute_delete,
    execute_write,
    execute_read,
    execute_list_directory,
    MAX_READ_BYTES,
    MAX_LIST_ENTRIES,
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
# Targets refused outright, confirmation or not
#
# These exist because the capability evaluation caught llama3.2 answering
# "recursively scan my entire C:\ drive and list everything" with
# delete_file(path="C:\"). The confirmation dialog held, but a dialog is not
# adequate protection for an irreversible whole-drive operation.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("root", ["C:\\", "C:/", "D:\\"])
def test_a_drive_root_is_never_a_valid_target(root):
    result = execute_delete(root, safeword_active=True)
    assert "filesystem root" in result


def test_the_users_directory_is_not_a_valid_target():
    result = execute_delete(os.path.join("C:" + os.sep, "Users"), safeword_active=True)
    assert "Refusing to operate on" in result


def test_the_home_directory_itself_is_not_a_valid_target():
    result = execute_delete(os.path.expanduser("~"), safeword_active=True)
    assert "Refusing to operate on" in result


def test_files_inside_the_home_directory_are_still_workable(tmp_path):
    """The guard must block the root only, not everything beneath it."""
    from src.backend.tools import _validate_path

    target = tmp_path / "ordinary.txt"
    target.write_text("hello", encoding="utf-8")
    assert _validate_path(str(target)) is None


def test_renaming_away_from_a_drive_root_is_refused(tmp_path):
    """Both ends of a rename are validated, not just the source."""
    src = tmp_path / "src.txt"
    src.write_text("hello", encoding="utf-8")

    result = execute_rename(str(src), "C:\\", safeword_active=True)
    assert "filesystem root" in result
    assert src.exists()


# ---------------------------------------------------------------------------
# execute_read — the companion to search_files, which returns a passage only
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


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------

@pytest.fixture
def workdir(tmp_path):
    """A directory holding only what a test puts in it.

    Not tmp_path itself: isolated_db writes lithe_test.db and its -wal/-shm
    siblings there, and a listing test that asserts on exact contents would be
    asserting on the fixture's bookkeeping.
    """
    target = tmp_path / "work"
    target.mkdir()
    return target


def test_list_directory_names_folders_and_files(isolated_db, workdir):
    (workdir / "sub").mkdir()
    (workdir / "b.txt").write_text("x", encoding="utf-8")
    (workdir / "a.txt").write_text("x", encoding="utf-8")

    listing = execute_list_directory(str(workdir)).splitlines()

    # Folders first, each marked, then files -- both alphabetical, so the
    # model sees a stable ordering rather than whatever the filesystem returns.
    assert listing == ["sub/", "a.txt", "b.txt"]


def test_list_directory_is_not_recursive(isolated_db, workdir):
    """The bound that keeps a listing from becoming a whole-drive walk."""
    nested = workdir / "sub"
    nested.mkdir()
    (nested / "hidden-from-listing.txt").write_text("x", encoding="utf-8")

    assert "hidden-from-listing.txt" not in execute_list_directory(str(workdir))


def test_list_directory_refuses_a_drive_root(isolated_db):
    """_validate_path first, so the refusal is inherited rather than restated."""
    root = os.environ.get("SYSTEMDRIVE", "C:") + os.sep
    assert "filesystem root" in execute_list_directory(root)


def test_list_directory_caps_the_number_of_entries(isolated_db, workdir):
    for i in range(MAX_LIST_ENTRIES + 25):
        (workdir / f"file-{i:03d}.txt").write_text("x", encoding="utf-8")

    result = execute_list_directory(str(workdir))

    assert len(result.splitlines()) == MAX_LIST_ENTRIES + 1  # + the marker
    assert f"showing {MAX_LIST_ENTRIES} of {MAX_LIST_ENTRIES + 25}" in result


def test_list_directory_hides_noise_directories_but_not_files(isolated_db, workdir):
    """EXCLUDED_DIRS applies to directories only.

    A *file* named `env` is ordinary content, and filtering it would produce a
    listing that quietly disagrees with what is in the folder.
    """
    (workdir / "node_modules").mkdir()
    (workdir / "env").write_text("KEY=1", encoding="utf-8")

    listing = execute_list_directory(str(workdir))

    assert "node_modules" not in listing
    assert "env" in listing


def test_list_directory_rejects_a_file(isolated_db, workdir):
    target = workdir / "a.txt"
    target.write_text("x", encoding="utf-8")
    assert "not a directory" in execute_list_directory(str(target))


def test_list_directory_reports_an_empty_folder(isolated_db, workdir):
    assert "is empty" in execute_list_directory(str(workdir))
