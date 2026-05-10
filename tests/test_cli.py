from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pdf2epub_recovery.cli import main
from tests.helpers import write_text_pdf


def test_help_runs(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert "pdf2epub-recovery" in output
    assert "profile" in output
    assert "convert" in output


def test_profile_writes_real_json(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(pdf, ["Hello from a native text PDF."])

    out = tmp_path / "profile.json"
    exit_code = main(["profile", str(pdf), "--out", str(out)])

    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["is_pdf"] is True
    assert payload["page_count"] == 1
    assert payload["native_text_page_count"] == 1
    assert payload["total_extracted_char_count"] > 0
    assert payload["likely_layout"] == "one_column"


def test_profile_rejects_non_pdf(tmp_path: Path) -> None:
    text = tmp_path / "not.pdf"
    text.write_text("not a pdf", encoding="utf-8")

    out = tmp_path / "profile.json"
    exit_code = main(["profile", str(text), "--out", str(out)])

    assert exit_code == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["is_pdf"] is False
    assert payload["warnings"][0]["code"] == "not_a_pdf"


def test_extract_writes_raw_blocks(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(pdf, ["First block text."])
    out = tmp_path / "extract.json"

    exit_code = main(["extract", str(pdf), "--out", str(out)])

    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    blocks = payload["extraction"]["pages"][0]["text_blocks"]
    assert blocks[0]["raw_text"]
    assert blocks[0]["bbox"]["x0"] >= 0
    assert blocks[0]["source_engine"] == "pymupdf"


def test_convert_creates_epub_and_report(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(
        pdf,
        [
            "This is a wrapped line example that should become readable.",
            "Second page keeps source order.",
            "Third page closes the fixture.",
        ],
        header="Sample Header",
        page_numbers=True,
    )
    epub = tmp_path / "book.epub"
    report = tmp_path / "book.report.json"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--report", str(report)])

    assert exit_code == 0
    assert epub.exists()
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert report_payload["status"] in {"ok", "warning"}
    assert report_payload["actions"]["page_numbers_removed"] == 3
    assert report_payload["actions"]["headers_removed"] == 3

    with zipfile.ZipFile(epub) as archive:
        xhtml = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xhtml")
        )
    assert "wrapped line example" in xhtml
    assert 'class="book"' in xhtml
    assert 'class="body-text"' in xhtml
    assert "Sample Header" not in xhtml
    assert ">1<" not in xhtml


def test_convert_keep_artifacts_keeps_headers(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(pdf, ["Body one.", "Body two."], header="Keep Header", page_numbers=True)
    epub = tmp_path / "book.epub"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--keep-artifacts"])

    assert exit_code == 0
    with zipfile.ZipFile(epub) as archive:
        xhtml = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xhtml")
        )
    assert "Keep Header" in xhtml


def test_convert_non_pdf_writes_error_report(tmp_path: Path) -> None:
    text = tmp_path / "not.pdf"
    text.write_text("not a pdf", encoding="utf-8")
    report = tmp_path / "error.report.json"

    exit_code = main(
        ["convert", str(text), "--out", str(tmp_path / "book.epub"), "--report", str(report)]
    )

    assert exit_code == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["warnings"][0]["code"] == "not_a_pdf"


def test_validate_reports_unconfigured_epubcheck(capsys, tmp_path: Path) -> None:
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"not really an epub")

    exit_code = main(["validate", str(epub)])

    assert exit_code in {0, 1, 2}
    output = capsys.readouterr().out
    if exit_code == 2:
        assert "EPUBCheck is not configured" in output
