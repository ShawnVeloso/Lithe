"""Text extraction for formats that cannot simply be read as UTF-8.

`index_file_content` opens a file with `encoding="utf-8", errors="strict"` and
stores what comes back. That is correct for the text formats in
CONTENT_INDEXED_EXTENSIONS and useless for a PDF, which is a container format
that happens to hold text. This module turns those containers into a plain
string the FTS5 index can hold.

**Nothing here may raise.** Extraction runs while walking a user's real drive,
where a malformed, encrypted, truncated or actively hostile file is ordinary.
One bad file must cost that file's content and nothing else -- not the walk,
and not the files after it.

The caps are the load-bearing part. A PDF has to be parsed before its text
length is known, so the byte cap that protects a text file protects nothing
here: a 300MB scanned document, a file with 40,000 pages, and a file with a
pathological cross-reference table all read as "small" until you are already
inside them.
"""

import os
import time
import xml.etree.ElementTree as ET
import zipfile

from src.backend.config import (
    BINARY_CONTENT_EXTENSIONS,
    BINARY_CONTENT_MAX_FILE_BYTES,
    EXTRACT_TIME_BUDGET_SECONDS,
    PDF_MAX_PAGES,
)
from src.backend.logger import logger

# WordprocessingML. A .docx is a zip; the body text lives in one entry.
_W_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCX_BODY = "word/document.xml"


def extract_text(file_path: str, ext: str, max_bytes: int) -> str | None:
    """The text inside a container format, or None if there is none to be had.

    Returns None for "not extractable" -- an unsupported extension, an
    unreadable file, an encrypted PDF, a scanned page with no text layer. The
    caller cannot distinguish those and does not need to: all of them mean the
    same thing, which is that this file is searchable by name only.
    """
    if ext not in BINARY_CONTENT_EXTENSIONS:
        return None

    try:
        size = os.path.getsize(file_path)
    except OSError:
        return None
    if size > BINARY_CONTENT_MAX_FILE_BYTES:
        logger.info(
            "Skipping content extraction for %s (%.1f MB exceeds the cap).",
            file_path, size / (1024 * 1024),
        )
        return None

    try:
        if ext == ".pdf":
            text = _extract_pdf(file_path, max_bytes)
        elif ext == ".docx":
            text = _extract_docx(file_path, max_bytes)
        else:
            return None
    except Exception:
        # Deliberately bare. pypdf alone raises PdfReadError, DependencyError,
        # KeyError, RecursionError and struct.error, and the point of this
        # module is that the caller never has to know which.
        logger.warning("Could not extract text from %s", file_path, exc_info=True)
        return None

    text = (text or "").strip()
    return text or None


def _extract_pdf(file_path: str, max_bytes: int) -> str:
    """Page text, up to whichever cap is reached first.

    pypdf is imported here rather than at module scope so that a Lithe start-up
    does not pay for it -- most sessions never touch a PDF. NOTE: that also
    hides it from PyInstaller's static analysis, which is why `pypdf` is a
    hiddenimport in lithe-server.spec. Without that entry this works perfectly
    in development and silently indexes nothing in the packaged build.
    """
    from pypdf import PdfReader

    reader = PdfReader(file_path)

    if reader.is_encrypted:
        # Most "encrypted" PDFs in the wild carry an empty owner password and
        # open fine; the ones that do not are simply skipped.
        try:
            if not reader.decrypt(""):
                return ""
        except Exception:
            return ""

    deadline = time.monotonic() + EXTRACT_TIME_BUDGET_SECONDS
    collected = []
    length = 0

    for index, page in enumerate(reader.pages):
        if index >= PDF_MAX_PAGES or length >= max_bytes:
            break
        if time.monotonic() > deadline:
            logger.info(
                "Extraction budget reached for %s after %d page(s).",
                file_path, index,
            )
            break
        try:
            page_text = page.extract_text() or ""
        except Exception:
            # One unparseable page does not condemn the rest of the document.
            continue
        if page_text:
            collected.append(page_text)
            length += len(page_text)

    return "\n".join(collected)[:max_bytes]


def _extract_docx(file_path: str, max_bytes: int) -> str:
    """Body text from a .docx, using only the standard library.

    python-docx would do this in one line, but it depends on lxml -- a compiled
    C extension, which means a wheel per platform and a PyInstaller hiddenimport
    to get wrong. A .docx is a zip with an XML entry; pulling the <w:t> nodes
    out of it needs neither.

    Word splits a run of text across several <w:t> nodes whenever formatting
    changes mid-sentence, so the nodes are joined without a separator and
    paragraphs are recovered from <w:p> instead. Joining every node with a space
    would put gaps inside words that a phrase search then could not match.
    """
    with zipfile.ZipFile(file_path) as archive:
        if _DOCX_BODY not in archive.namelist():
            return ""
        with archive.open(_DOCX_BODY) as body:
            tree = ET.parse(body)

    paragraphs = []
    length = 0
    for para in tree.iter(f"{_W_NAMESPACE}p"):
        text = "".join(
            node.text or "" for node in para.iter(f"{_W_NAMESPACE}t")
        )
        if not text:
            continue
        paragraphs.append(text)
        length += len(text)
        if length >= max_bytes:
            break

    return "\n".join(paragraphs)[:max_bytes]
