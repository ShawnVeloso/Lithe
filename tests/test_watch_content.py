"""The watcher must content-index, not just record metadata.

`walk_and_index` reads a file's text into the FTS5 index; the watcher builds its
own record and calls `upsert_files` directly. So a file created or edited while
Lithe was running stayed searchable by name only until the next restart -- the
content index silently lagged the filesystem for the entire session, which is
the half of the day a desktop assistant is actually used.
"""

import pytest

from src.backend import memory, watcher


@pytest.fixture
def handler(isolated_db, tmp_path, monkeypatch):
    """A watcher handler pointed at a throwaway directory."""
    monkeypatch.setattr(watcher, "INDEX_WHITELIST", [str(tmp_path)])
    return watcher._LitheEventHandler()


def write(tmp_path, name, text):
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def test_a_file_created_while_running_is_searchable_by_content(handler, tmp_path):
    target = write(tmp_path, "notes.md", "the internal code word is ZEPHYR-441\n")

    handler._execute("create", str(target))

    hits = memory.search_files_by_content("ZEPHYR-441")
    assert [h["path"] for h in hits] == [str(target)]


def test_an_edit_replaces_the_indexed_content(handler, tmp_path):
    target = write(tmp_path, "notes.md", "the secret is ALPHA\n")
    handler._execute("create", str(target))

    target.write_text("the secret is BETA\n", encoding="utf-8")
    handler._execute("upsert", str(target))

    assert memory.search_files_by_content("BETA")
    # Stale text must stop matching, or search reports content the file lost.
    assert memory.search_files_by_content("ALPHA") == []


def test_an_uppercase_extension_is_still_content_indexed(handler, tmp_path):
    """CONTENT_INDEXED_EXTENSIONS is lowercase; the watcher's ext was not.

    The extension is only lowercased inside the record dict, so passing the raw
    value through would skip `.MD` while `.md` worked -- a difference no user
    would ever guess at.
    """
    target = write(tmp_path, "READY.MD", "deployment token OMEGA-77\n")

    handler._execute("create", str(target))

    assert memory.search_files_by_content("OMEGA-77")


def test_deleting_a_watched_file_clears_its_content(handler, tmp_path):
    target = write(tmp_path, "notes.md", "the secret is ALPHA\n")
    handler._execute("create", str(target))

    handler._execute("delete", str(target))

    assert memory.search_files_by_content("ALPHA") == []


def test_a_non_indexed_extension_is_recorded_but_not_read(handler, tmp_path):
    """The allowlist still applies; the watcher must not widen it."""
    target = write(tmp_path, "bundle.zip", "ZEPHYR-441 pretending to be a zip\n")

    handler._execute("create", str(target))

    assert memory.search_files_by_content("ZEPHYR-441") == []
    assert memory.search_files_by_name("bundle")   # metadata still indexed


def test_an_unreadable_file_does_not_break_the_watcher(handler, tmp_path):
    """One bad file must not stop the handler from recording the rest."""
    target = tmp_path / "broken.md"
    target.write_bytes(b"\xff\xfe\x00not decodable as utf-8")

    handler._execute("create", str(target))

    assert memory.search_files_by_name("broken")
