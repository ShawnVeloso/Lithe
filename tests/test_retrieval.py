"""Tests for the file-context injection path (F-04).

These quantify what retrieval can and cannot do. Several assert the *current*
limits rather than desired behaviour — they are the measured ceiling, and they
will need updating when content indexing lands. Each says so explicitly.
"""

import pytest

from src.backend import brain
from src.backend.memory import search_files_by_name
from src.backend.retrieval import (
    MAX_FILE_SIZE_BYTES,
    extract_filenames,
    get_file_contexts,
    read_file_securely,
)
from tests.support.fake_gemini import text_response


# ---------------------------------------------------------------------------
# What triggers retrieval at all
# ---------------------------------------------------------------------------

def test_message_without_a_filename_retrieves_nothing(indexed_workspace):
    """The coverage ceiling: retrieval only fires on a literal `name.ext` token.

    A question phrased the way a person actually asks it injects no context at
    all, because extract_filenames finds nothing to look up.
    """
    indexed_workspace.add("budget.csv", "month,spend\njan,100\n")
    assert get_file_contexts("what did I write about the budget last week?") == ""


def test_named_file_is_injected_with_its_content(indexed_workspace):
    indexed_workspace.add("budget.csv", "month,spend\njan,100\n")
    context = get_file_contexts("summarize budget.csv")
    assert "LOCAL FILE CONTEXT: budget.csv" in context
    assert "jan,100" in context


def test_unindexed_filename_produces_a_system_note(indexed_workspace):
    context = get_file_contexts("summarize nowhere.csv")
    assert "not found in the indexed directories" in context
    assert "nowhere.csv" in context


def test_version_numbers_are_mistaken_for_filenames(indexed_workspace):
    """extract_filenames matches any word.ext token, so prose trips it.

    The consequence is a misleading "file not found" note glued onto an
    otherwise ordinary question.
    """
    assert "3.11" in extract_filenames("I am on python 3.11 now")
    context = get_file_contexts("I am on python 3.11 now")
    assert "not found in the indexed directories" in context


# ---------------------------------------------------------------------------
# Ranking and volume
# ---------------------------------------------------------------------------

def test_basename_collision_injects_every_match(indexed_workspace):
    """find_file_paths has no LIMIT and no ranking, so ambiguity multiplies.

    Mentioning a common filename pulls in every indexed copy, each up to 100KB.
    """
    indexed_workspace.add("project_a/config.json", '{"which": "a"}')
    indexed_workspace.add("project_b/config.json", '{"which": "b"}')

    context = get_file_contexts("what is in config.json?")
    assert '{"which": "a"}' in context
    assert '{"which": "b"}' in context
    assert context.count("LOCAL FILE CONTEXT: config.json") == 2


def test_large_file_is_truncated_from_the_head(indexed_workspace):
    """Truncation keeps the first 100KB, so the tail is invisible to the model."""
    marker = "TAIL_MARKER_XYZ"
    body = ("a" * 1000 + "\n") * 120  # comfortably over MAX_FILE_SIZE_BYTES
    target = indexed_workspace.add("big.txt", body + marker)
    assert target.stat().st_size > MAX_FILE_SIZE_BYTES

    content, truncated = read_file_securely(str(target))
    assert truncated is True
    assert "[FILE TRUNCATED DUE TO SIZE]" in content
    assert marker not in content, "tail unexpectedly survived truncation"


def test_binary_file_yields_a_placeholder_not_content(indexed_workspace):
    """A PDF or image is indexed and injectable, but reads as a placeholder.

    The system prompt tells the model to trust injected content, so this is the
    setup for a confident answer about a file it cannot actually see.
    """
    target = indexed_workspace.add("logo.png", b"\x89PNG\r\n\x1a\n\xff\xfe\xfd", binary=True)
    content, _ = read_file_securely(str(target))
    assert content == "[Binary or Unsupported File Format]"


# ---------------------------------------------------------------------------
# search_files: what it can actually answer
# ---------------------------------------------------------------------------

def test_search_files_cannot_see_file_contents(indexed_workspace):
    """The index stores metadata only — there is no content column.

    A file whose *body* contains the search term is invisible.
    """
    indexed_workspace.add("notes.txt", "the quarterly revenue discussion")

    assert search_files_by_name("notes") != []
    assert search_files_by_name("quarterly") == [], (
        "content search unexpectedly worked — has a content index been added?"
    )


@pytest.mark.xfail(
    strict=True,
    reason="B4: search_files' docstring tells the model it finds files that "
           "CONTAIN a word, but it only matches filenames",
)
def test_search_files_description_does_not_promise_content_search(
    isolated_db, scripted_gemini
):
    """A tool description that overpromises causes confident wrong answers."""
    client = scripted_gemini([text_response("hi")])
    brain.chat("hello")

    tools = client.calls[0]["config"].tools
    search_tool = next(t for t in tools if t.__name__ == "search_files")
    doc = (search_tool.__doc__ or "").lower()

    assert "contain" not in doc, (
        "search_files claims to find files containing a word; it matches names only"
    )
