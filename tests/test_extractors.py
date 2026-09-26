"""Text extraction from PDF and DOCX, and the caps that make it safe.

Extraction runs while walking a user's real drive. The parsing is the easy
part; what matters is that a malformed, encrypted, enormous or actively hostile
file costs that one file's content and nothing else. `index_file_content`
promises never to raise, and routing PDFs through its UTF-8 path would have
broken that promise -- pypdf raises PdfReadError, RecursionError and
struct.error, none of which its `except (UnicodeDecodeError, OSError,
ValueError)` would have caught.

Fixtures are built in code (tests/support/binary_fixtures.py) rather than
committed as binaries, so "a corrupt PDF" is corrupt in a way you can read.
"""

import zipfile

import pytest

from src.backend import extractors, indexer, memory
from src.backend.config import CONTENT_INDEX_MAX_BYTES
from tests.support.binary_fixtures import (
    write_docx,
    write_encrypted_pdf,
    write_pdf,
    write_truncated_pdf,
)

CAP = CONTENT_INDEX_MAX_BYTES


# --- The happy paths -------------------------------------------------------


def test_a_pdf_gives_up_its_text(tmp_path):
    target = write_pdf(tmp_path / "notes.pdf", ["The internal code word is ZEPHYR-441"])

    assert "ZEPHYR-441" in extractors.extract_text(str(target), ".pdf", CAP)


def test_a_multi_page_pdf_returns_every_page(tmp_path):
    target = write_pdf(tmp_path / "report.pdf", ["FIRST_PAGE", "SECOND_PAGE"])

    text = extractors.extract_text(str(target), ".pdf", CAP)

    assert "FIRST_PAGE" in text and "SECOND_PAGE" in text


def test_a_docx_gives_up_its_text(tmp_path):
    target = write_docx(tmp_path / "memo.docx", ["The internal code word is ZEPHYR-441"])

    assert "ZEPHYR-441" in extractors.extract_text(str(target), ".docx", CAP)


def test_docx_runs_are_joined_without_inserting_gaps(tmp_path):
    """Word splits a sentence across <w:t> nodes wherever formatting changes.

    Joining those with a space would put gaps inside words, and a phrase search
    -- which is how every content query is issued -- would then never match.
    """
    target = write_docx(tmp_path / "split.docx", ["ZEPHYR-441"], split_runs=True)

    assert extractors.extract_text(str(target), ".docx", CAP) == "ZEPHYR-441"


def test_docx_paragraphs_stay_separated(tmp_path):
    target = write_docx(tmp_path / "two.docx", ["first line", "second line"])

    assert extractors.extract_text(str(target), ".docx", CAP) == "first line\nsecond line"


# --- The failures that must stay quiet -------------------------------------


def test_an_encrypted_pdf_is_skipped_rather_than_raising(tmp_path):
    target = write_encrypted_pdf(tmp_path / "locked.pdf", "SECRET_MARKER", "hunter2")

    assert extractors.extract_text(str(target), ".pdf", CAP) is None


def test_a_truncated_pdf_is_skipped_rather_than_raising(tmp_path):
    target = write_truncated_pdf(tmp_path / "broken.pdf")

    assert extractors.extract_text(str(target), ".pdf", CAP) is None


def test_a_docx_that_is_not_a_zip_is_skipped(tmp_path):
    target = tmp_path / "fake.docx"
    target.write_text("this is just text pretending to be a document", encoding="utf-8")

    assert extractors.extract_text(str(target), ".docx", CAP) is None


def test_a_zip_without_a_document_body_is_skipped(tmp_path):
    """A valid zip with the wrong contents is not a Word file."""
    target = tmp_path / "empty.docx"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("hello.txt", "nothing useful here")

    assert extractors.extract_text(str(target), ".docx", CAP) is None


def test_a_missing_file_is_skipped(tmp_path):
    assert extractors.extract_text(str(tmp_path / "nope.pdf"), ".pdf", CAP) is None


def test_an_unsupported_extension_is_not_attempted(tmp_path):
    target = tmp_path / "archive.zip"
    target.write_bytes(b"PK\x03\x04 whatever")

    assert extractors.extract_text(str(target), ".zip", CAP) is None


def test_a_pdf_with_no_text_layer_yields_nothing(tmp_path):
    """A scanned document is pages of pixels. Empty is the honest answer."""
    from pypdf import PdfWriter

    target = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(target, "wb") as handle:
        writer.write(handle)

    assert extractors.extract_text(str(target), ".pdf", CAP) is None


# --- The caps --------------------------------------------------------------


def test_an_oversized_file_is_not_opened(tmp_path, monkeypatch):
    """The size check must come before the parser, not after."""
    target = write_pdf(tmp_path / "big.pdf", ["ZEPHYR-441"])
    monkeypatch.setattr(extractors, "BINARY_CONTENT_MAX_FILE_BYTES", 10)

    def explode(*args, **kwargs):
        raise AssertionError("the parser was reached despite the size cap")

    monkeypatch.setattr(extractors, "_extract_pdf", explode)

    assert extractors.extract_text(str(target), ".pdf", CAP) is None


def test_only_the_first_pages_of_a_long_pdf_are_read(tmp_path, monkeypatch):
    monkeypatch.setattr(extractors, "PDF_MAX_PAGES", 2)
    target = write_pdf(
        tmp_path / "long.pdf", ["PAGE_ONE", "PAGE_TWO", "PAGE_THREE", "PAGE_FOUR"]
    )

    text = extractors.extract_text(str(target), ".pdf", CAP)

    assert "PAGE_ONE" in text and "PAGE_TWO" in text
    assert "PAGE_THREE" not in text


def test_extraction_stops_at_the_byte_cap(tmp_path):
    target = write_pdf(tmp_path / "wide.pdf", ["A" * 400])

    text = extractors.extract_text(str(target), ".pdf", 50)

    assert len(text) <= 50


def test_the_time_budget_stops_a_slow_document(tmp_path, monkeypatch):
    """A pathological cross-reference table can make one page take minutes."""
    monkeypatch.setattr(extractors, "EXTRACT_TIME_BUDGET_SECONDS", -1)
    target = write_pdf(tmp_path / "slow.pdf", ["PAGE_ONE", "PAGE_TWO"])

    assert extractors.extract_text(str(target), ".pdf", CAP) is None


# --- Into the index --------------------------------------------------------


def test_a_pdf_becomes_searchable_by_its_contents(isolated_db, tmp_path):
    target = write_pdf(tmp_path / "meeting.pdf", ["The code word is ZEPHYR-441"])
    memory.upsert_files([{
        "path": str(target), "name": target.name, "extension": ".pdf",
        "size_bytes": target.stat().st_size, "modified_at": 1.0,
        "indexed_at": 1.0, "category": "",
    }])

    assert indexer.index_file_content(str(target), ".pdf") is True
    found = memory.search_files_by_content("ZEPHYR-441")
    assert [h["name"] for h in found] == ["meeting.pdf"]


@pytest.fixture
def corpus(isolated_db, tmp_path, monkeypatch):
    """A directory of good and bad documents, wired as the index root."""
    from src.backend import config as lithe_config

    write_truncated_pdf(tmp_path / "broken.pdf")
    write_pdf(tmp_path / "good.pdf", ["SURVIVOR_MARKER"])
    write_docx(tmp_path / "notes.docx", ["ALSO_SURVIVED"])
    (tmp_path / "plain.md").write_text("PLAIN_TEXT_MARKER\n", encoding="utf-8")

    monkeypatch.setattr(lithe_config, "INDEX_WHITELIST", [str(tmp_path)])
    monkeypatch.setattr(indexer, "INDEX_WHITELIST", [str(tmp_path)])
    return tmp_path


def test_the_walk_indexes_text_but_defers_documents(corpus):
    """The ordering guarantee, asserted rather than assumed.

    server.py runs walk -> start_watcher -> backfill. If the walk extracted
    documents inline, a drive with a few thousand PDFs would sit between
    start-up and the watcher existing, and every file change made in that
    window would be lost with nothing to show it happened.
    """
    indexer.walk_and_index()

    assert memory.search_files_by_content("PLAIN_TEXT_MARKER")
    # Known by name immediately; their text has not been read yet.
    assert memory.search_files_by_name("good")
    assert memory.search_files_by_content("SURVIVOR_MARKER") == []
    assert memory.search_files_by_content("ALSO_SURVIVED") == []


def test_the_backfill_extracts_what_the_walk_deferred(corpus):
    indexer.walk_and_index()

    extracted = indexer.backfill_binary_content()

    assert extracted == 2                      # the good PDF and the docx
    assert memory.search_files_by_content("SURVIVOR_MARKER")
    assert memory.search_files_by_content("ALSO_SURVIVED")


def test_one_broken_document_does_not_stop_the_backfill(corpus):
    """A bad file on a real drive must cost only that file."""
    indexer.walk_and_index()

    indexer.backfill_binary_content()

    assert memory.search_files_by_content("SURVIVOR_MARKER")
    # The broken one is still known by name -- only its content is missing.
    assert memory.search_files_by_name("broken")
    assert memory.search_files_by_content("broken") == []


def test_the_backfill_does_no_work_twice(corpus):
    """paths_missing_content is what keeps a restart from re-parsing everything."""
    indexer.walk_and_index()
    assert indexer.backfill_binary_content() == 2

    assert indexer.backfill_binary_content() == 0


def test_index_file_content_never_raises_on_a_bad_pdf(isolated_db, tmp_path):
    """The promise in its docstring, tested rather than trusted."""
    target = write_truncated_pdf(tmp_path / "broken.pdf")

    assert indexer.index_file_content(str(target), ".pdf") is False


# --- read_file ------------------------------------------------------------


def test_read_file_returns_the_text_of_a_pdf(isolated_db, tmp_path):
    """Search can find a PDF by its contents, so reading one must work too.

    Otherwise the model can locate a document and say nothing about it, which
    is a worse dead end than never finding it.
    """
    from src.backend.tools import execute_read

    target = write_pdf(tmp_path / "report.pdf", ["Quarterly revenue rose to 4.2M"])

    assert "Quarterly revenue" in execute_read(str(target))


def test_read_file_returns_the_text_of_a_docx(isolated_db, tmp_path):
    from src.backend.tools import execute_read

    target = write_docx(tmp_path / "memo.docx", ["Attendees agreed the timeline"])

    assert "Attendees agreed" in execute_read(str(target))


def test_read_file_explains_an_unreadable_document(isolated_db, tmp_path):
    """An encrypted PDF is a different problem from a JPEG, and says so."""
    from src.backend.tools import execute_read

    target = write_encrypted_pdf(tmp_path / "locked.pdf", "SECRET", "hunter2")

    result = execute_read(str(target))

    assert result.startswith("ERROR")
    assert "encrypted" in result
