"""Tests for the FTS5 content index (`retrieval-by-content`).

Until this landed, `search_files` matched filenames only. Its description once
claimed otherwise, and correcting that claim rather than the behaviour is what
left the capability missing: a user asking "which file mentions ZEPHYR-441?"
got nothing, because nothing in Lithe had ever read the inside of a file it was
not already told to open.

What is deliberately *not* indexed is as load-bearing as what is. Content
indexing reads and stores bytes, so the extension list is an allowlist, only
the first 100KB of a file is searchable, and a file whose text does not decode
is left out rather than stored as replacement characters.
"""

import pytest

from src.backend import config, indexer, memory


@pytest.fixture
def workspace(indexed_workspace):
    return indexed_workspace


# --- Storage ---------------------------------------------------------------


def test_a_file_is_found_by_its_contents(workspace):
    workspace.add("notes_meeting.md", "The agreed internal code word is ZEPHYR-441.\n")
    workspace.add("unrelated.md", "Nothing to see here.\n")

    hits = memory.search_files_by_content("ZEPHYR-441")

    assert [h["name"] for h in hits] == ["notes_meeting.md"]
    assert "ZEPHYR-441" in hits[0]["excerpt"]


def test_a_hyphenated_term_is_searched_literally(workspace):
    """Bare user text is an FTS5 query language, not a search string.

    Unquoted, `ZEPHYR-441` parses as `ZEPHYR NOT 441` — which happens to match
    here for the wrong reason, so the case that proves quoting works is a term
    whose halves live in different files.
    """
    workspace.add("alpha.md", "ZEPHYR appears alone here.\n")
    workspace.add("beta.md", "441 appears alone here.\n")
    workspace.add("gamma.md", "ZEPHYR-441 appears whole here.\n")

    assert [h["name"] for h in memory.search_files_by_content("ZEPHYR-441")] == ["gamma.md"]


def test_an_unparseable_term_returns_nothing_rather_than_raising(workspace):
    """Search is reached through a tool call, where an exception is opaque."""
    workspace.add("alpha.md", "ordinary text\n")

    for term in ['"', 'a AND', '*', 'NEAR(']:
        assert memory.search_files_by_content(term) == []


def test_an_empty_term_matches_nothing(workspace):
    workspace.add("alpha.md", "ordinary text\n")
    assert memory.search_files_by_content("   ") == []


def test_reindexing_replaces_content_rather_than_adding_to_it(workspace):
    """FTS5 has no UPSERT; without an explicit delete a file accumulates copies."""
    target = workspace.add("notes.md", "the secret is ALPHA\n")

    target.write_text("the secret is BETA\n", encoding="utf-8")
    indexer.index_file_content(str(target), ".md")

    assert memory.search_files_by_content("BETA")
    # The old text must stop matching, or search reports content the file no
    # longer has.
    assert memory.search_files_by_content("ALPHA") == []


def test_deleting_a_file_removes_its_content(workspace):
    target = workspace.add("notes.md", "the secret is ALPHA\n")

    memory.delete_file_by_path(str(target))

    assert memory.search_files_by_content("ALPHA") == []


def test_deleting_by_paths_removes_content_too(workspace):
    target = workspace.add("notes.md", "the secret is ALPHA\n")

    memory.delete_files_by_paths([str(target)])

    assert memory.search_files_by_content("ALPHA") == []


def test_content_without_a_file_record_is_not_returned(workspace):
    """A stale FTS row must not hand the model a path the index has dropped."""
    memory.upsert_file_content("C:\gone\vanished.md", "ZEPHYR-441 lives here")

    assert memory.search_files_by_content("ZEPHYR-441") == []


# --- What gets indexed -----------------------------------------------------


def test_only_allowlisted_extensions_are_content_indexed(tmp_path, isolated_db):
    target = tmp_path / "archive.zip"
    target.write_text("ZEPHYR-441", encoding="utf-8")

    assert indexer.index_file_content(str(target), ".zip") is False
    assert memory.search_files_by_content("ZEPHYR-441") == []


def test_a_text_extension_that_does_not_decode_is_skipped(tmp_path, isolated_db):
    """Storing replacement characters would match nothing anyone would search."""
    target = tmp_path / "broken.md"
    target.write_bytes(b"\xff\xfe\x00binary pretending to be markdown")

    assert indexer.index_file_content(str(target), ".md") is False


def test_an_empty_file_is_not_indexed(tmp_path, isolated_db):
    target = tmp_path / "blank.md"
    target.write_text("   \n\n", encoding="utf-8")

    assert indexer.index_file_content(str(target), ".md") is False


def test_a_missing_file_does_not_end_the_walk(tmp_path, isolated_db):
    """One unreadable file on a real drive must not abort indexing."""
    assert indexer.index_file_content(str(tmp_path / "nope.md"), ".md") is False


def test_only_the_head_of_a_large_file_is_searchable(tmp_path, isolated_db):
    """The cap matches retrieval's, so a match can always be quoted back."""
    target = tmp_path / "big.txt"
    filler = "lorem ipsum dolor sit amet " * 6000   # comfortably over 100KB
    target.write_text("HEAD_MARKER\n" + filler + "\nTAIL_MARKER_OMEGA\n", encoding="utf-8")
    memory.upsert_files([{
        "path": str(target), "name": target.name, "extension": ".txt",
        "size_bytes": target.stat().st_size, "modified_at": 1.0,
        "indexed_at": 1.0, "category": "",
    }])

    assert indexer.index_file_content(str(target), ".txt") is True
    assert memory.search_files_by_content("HEAD_MARKER")
    # Past the cap. Not finding it is the honest outcome: retrieval could not
    # show the passage either.
    assert memory.search_files_by_content("TAIL_MARKER_OMEGA") == []


def test_the_index_cap_matches_what_retrieval_will_show(isolated_db):
    """Two constants, one meaning. Drift would let search promise more than
    retrieval can quote."""
    from src.backend.retrieval import MAX_FILE_SIZE_BYTES

    assert config.CONTENT_INDEX_MAX_BYTES == MAX_FILE_SIZE_BYTES


# --- Backfill --------------------------------------------------------------


def test_paths_missing_content_finds_the_unindexed(workspace):
    """An existing install must backfill; reconciliation skips unchanged files."""
    indexed = workspace.add("has_content.md", "ZEPHYR-441\n")
    bare = workspace.add("no_content.zip", "not indexed by extension\n")

    missing = memory.paths_missing_content([str(indexed), str(bare)])

    assert missing == [str(bare)]


def test_paths_missing_content_handles_more_than_one_batch(workspace):
    """Chunked to stay under SQLite's variable limit."""
    paths = [f"C:\none\file{n}.md" for n in range(900)]

    assert memory.paths_missing_content(paths) == paths
    assert memory.paths_missing_content([]) == []


# --- The tool the model actually calls --------------------------------------


def _search(keyword):
    """Call the real search_files closure, as the agent loop would."""
    from src.backend import brain

    tools = {fn.__name__: fn for fn in brain._build_tool_functions()}
    return tools["search_files"](keyword)


def test_search_files_finds_a_file_by_its_contents(workspace):
    """The capability `retrieval-by-content` was waiting on."""
    workspace.add("notes_meeting.md", "The agreed internal code word is ZEPHYR-441.\n")

    result = _search("ZEPHYR-441")

    assert "notes_meeting.md" in result
    assert "matched text:" in result


def test_search_files_still_matches_names(workspace):
    """The original behaviour is not traded away for the new one."""
    workspace.add("quarterly_budget.csv", "month,revenue\n2026-01,100\n")

    result = _search("budget")

    assert "quarterly_budget.csv" in result


def test_a_name_match_is_not_repeated_as_a_content_match(workspace):
    """One file, one line — and no excerpt for a file matched by its name."""
    workspace.add("zephyr.md", "zephyr appears in the body as well\n")

    result = _search("zephyr")

    # The name appears twice per line (name, then full path), so count rows.
    assert "Found 1 file(s)" in result
    assert "matched text:" not in result


def test_name_matches_are_listed_before_content_matches(workspace):
    workspace.add("mentions_it.md", "this one only mentions zephyr in the body\n")
    workspace.add("zephyr.md", "unrelated body text\n")

    result = _search("zephyr")

    assert result.index("zephyr.md") < result.index("mentions_it.md")


def test_no_match_still_says_so(workspace):
    workspace.add("notes.md", "nothing relevant\n")

    assert "No files found" in _search("ZEPHYR-441")
