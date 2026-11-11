from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.services import documents
from app.services.documents import DocumentError, chunk_segments, parse_document, validate_upload


def test_upload_validation_requires_safe_extension_and_signature() -> None:
    assert validate_upload("notes.txt", b"hello", "text/plain") == (".txt", "text/plain")
    with pytest.raises(DocumentError, match="UNSUPPORTED_FILE_TYPE"):
        validate_upload("script.html", b"<script>alert(1)</script>", "text/html")
    with pytest.raises(DocumentError, match="FILE_SIGNATURE_MISMATCH"):
        validate_upload("report.pdf", b"plain text", "application/pdf")


def test_extract_text_and_csv_source_locators(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("မင်္ဂလာပါ\nPyChat private evidence", encoding="utf-8")
    parsed = parse_document(text_path, ".txt")
    assert parsed.status == "ready"
    assert "မင်္ဂလာပါ" in parsed.segments[0].text

    csv_path = tmp_path / "table.csv"
    csv_path.write_text("name,city\nKim,ရန်ကုန်\n", encoding="utf-8")
    csv = parse_document(csv_path, ".csv")
    assert csv.segments[1].source_locator == {"type": "row", "row": 2}


def test_empty_pdf_is_reported_as_ocr_required(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with path.open("wb") as output:
        writer.write(output)
    assert parse_document(path, ".pdf").status == "ocr_required"


def test_chunking_preserves_nonempty_bounded_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(documents, "tiktoken", None)
    segments = [
        documents.ParsedSegment(
            "မင်္ဂလာပါ " + ("evidence " * 200), 2, {"type": "page", "page": 2}
        )
    ]
    chunks = chunk_segments(segments)
    assert chunks
    assert all(chunk.content and chunk.token_count > 0 for chunk in chunks)
    assert all(chunk.source_locator["type"] == "page" for chunk in chunks)


def test_storage_key_cannot_escape_private_root() -> None:
    with pytest.raises(DocumentError, match="INVALID_STORAGE_KEY"):
        documents.storage_path("../../outside")
