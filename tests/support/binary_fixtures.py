"""Valid PDF and DOCX files built in code, not committed as binary blobs.

A checked-in binary fixture is unreviewable: nobody can tell from a diff what
changed inside it, or whether the "corrupt PDF" case is corrupt in the way the
test claims. These are small enough to read.
"""

import zipfile

_DOCX_BODY_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{paragraphs}</w:body>
</w:document>"""

# Word splits a run wherever formatting changes, so a single sentence can arrive
# as several <w:t> nodes. The extractor must join them without a separator.
_DOCX_PARAGRAPH = "<w:p><w:r>{runs}</w:r></w:p>"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""


def write_docx(path, paragraphs, split_runs=False):
    """A minimal but genuinely valid .docx.

    `split_runs` chops each paragraph into one <w:t> per character, reproducing
    the fragmentation Word actually produces. A extractor that joins nodes with
    a space passes the simple case and fails this one.
    """
    body = []
    for text in paragraphs:
        if split_runs:
            runs = "".join(f"<w:t>{c}</w:t>" for c in text)
        else:
            runs = f"<w:t>{text}</w:t>"
        body.append(_DOCX_PARAGRAPH.format(runs=runs))

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr(
            "word/document.xml",
            _DOCX_BODY_TEMPLATE.format(paragraphs="".join(body)),
        )
    return path


def write_pdf(path, pages):
    """A real PDF, built with pypdf so the bytes are what a reader expects.

    Text is drawn with a content stream rather than a helper, because pypdf is a
    reader-first library and its writer has no "add a paragraph" call.
    """
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject

    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        stream = DecodedStreamObject()
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream.set_data(
            f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
        )
        font = DictionaryObject()
        font.update({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        resources = DictionaryObject()
        fonts = DictionaryObject()
        fonts[NameObject("/F1")] = writer._add_object(font)
        resources[NameObject("/Font")] = fonts
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(stream)

    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def write_encrypted_pdf(path, text, password):
    """A PDF that genuinely will not open without a password."""
    from pypdf import PdfWriter

    write_pdf(path, [text])
    writer = PdfWriter(clone_from=str(path))
    writer.encrypt(password)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def write_truncated_pdf(path):
    """Starts like a PDF, ends mid-object. pypdf raises on this."""
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendo")
    return path
