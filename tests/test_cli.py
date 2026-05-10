from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pdf2epub_recovery.cli import main
from tests.helpers import (
    write_text_and_image_pdf,
    write_text_pdf,
    write_text_table_pdf,
    write_uncertain_text_table_pdf,
)


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


def test_convert_writes_debug_artifacts(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(
        pdf,
        ["Body page one.", "Body page two.", "Body page three."],
        header="Debug Header",
        page_numbers=True,
    )
    epub = tmp_path / "book.epub"
    debug_dir = tmp_path / "debug"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--debug-dir", str(debug_dir)])

    assert exit_code == 0
    removed_payload = json.loads((debug_dir / "removed-artifacts.json").read_text(encoding="utf-8"))
    assert removed_payload["counts_by_type"]["page_number"] == 3
    assert removed_payload["counts_by_type"]["header"] == 3
    assert removed_payload["removed_artifacts"][0]["bbox"]["x0"] >= 0
    assert removed_payload["removed_artifacts"][0]["reason"]
    assert removed_payload["removed_artifacts"][0]["confidence"] > 0

    ordered_payload = json.loads((debug_dir / "ordered-blocks.json").read_text(encoding="utf-8"))
    assert ordered_payload["block_count"] == 3
    assert [block["order_index"] for block in ordered_payload["ordered_blocks"]] == [0, 1, 2]
    assert "Body page one" in ordered_payload["ordered_blocks"][0]["text"]
    assert ordered_payload["ordered_blocks"][0]["source_engine"] == "pymupdf"

    kept_margin_payload = json.loads(
        (debug_dir / "kept-margin-blocks.json").read_text(encoding="utf-8")
    )
    assert kept_margin_payload == {"block_count": 0, "kept_margin_blocks": []}
    assert not (debug_dir / "table-fallbacks.json").exists()


def test_convert_writes_kept_margin_debug_for_single_page_margin_text(tmp_path: Path) -> None:
    pdf_single = tmp_path / "single.pdf"
    write_text_pdf(pdf_single, ["Only page body."], header="Single Header", page_numbers=True)
    debug_single = tmp_path / "debug-single"
    exit_code = main(
        [
            "convert",
            str(pdf_single),
            "--out",
            str(tmp_path / "single.epub"),
            "--debug-dir",
            str(debug_single),
        ]
    )

    assert exit_code == 0
    single_payload = json.loads(
        (debug_single / "kept-margin-blocks.json").read_text(encoding="utf-8")
    )
    assert single_payload["block_count"] == 2
    assert {block["margin_zone"] for block in single_payload["kept_margin_blocks"]} == {
        "top",
        "bottom",
    }
    assert all(block["kept_reason"] for block in single_payload["kept_margin_blocks"])


def test_convert_preserves_simple_embedded_image(tmp_path: Path) -> None:
    pdf = tmp_path / "sample-image.pdf"
    write_text_and_image_pdf(pdf)
    epub = tmp_path / "book.epub"
    report = tmp_path / "book.report.json"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--report", str(report)])

    assert exit_code == 0
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert report_payload["actions"]["images_detected"] == 1
    assert report_payload["actions"]["images_preserved"] == 1
    assert report_payload["actions"]["images_not_preserved"] == 0

    with zipfile.ZipFile(epub) as archive:
        names = archive.namelist()
        xhtml = "\n".join(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".xhtml")
        )

    assert any(name.endswith(".png") for name in names)
    assert "<figure" in xhtml
    assert '<img src="../images/' in xhtml
    assert "Image from page 1" in xhtml


def test_convert_writes_image_debug_artifacts(tmp_path: Path) -> None:
    pdf = tmp_path / "sample-image.pdf"
    write_text_and_image_pdf(pdf)
    epub = tmp_path / "book.epub"
    debug_dir = tmp_path / "debug"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--debug-dir", str(debug_dir)])

    assert exit_code == 0
    payload = json.loads((debug_dir / "images.json").read_text(encoding="utf-8"))
    assert payload["image_count"] == 1
    image = payload["images"][0]
    assert image["image_id"].startswith("p0001-img")
    assert image["placement"]["bbox"]["x0"] >= 0
    assert image["provenance"]["source_engine"] == "pymupdf"
    assert image["preservation"]["status"] == "preserved"
    assert image["preservation"]["file_name"].startswith("images/")
    assert image["preservation"]["byte_count"] > 0


def test_convert_renders_obvious_text_table_semantically(tmp_path: Path) -> None:
    pdf = tmp_path / "sample-table.pdf"
    write_text_table_pdf(pdf)
    epub = tmp_path / "book.epub"
    report = tmp_path / "book.report.json"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--report", str(report)])

    assert exit_code == 0
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert report_payload["actions"]["table_like_blocks_detected"] == 1
    assert report_payload["actions"]["tables_rendered_semantically"] == 1
    assert report_payload["actions"]["table_fallbacks_rendered"] == 0
    assert not any(
        warning["code"] == "table_fallback_used" for warning in report_payload["warnings"]
    )

    with zipfile.ZipFile(epub) as archive:
        xhtml = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xhtml")
        )

    assert '<figure class="table"><table>' in xhtml
    assert "<th>Name</th>" in xhtml
    assert "<td>Ada</td>" in xhtml
    assert 'class="body-text">Name' not in xhtml


def test_convert_writes_table_fallback_debug_when_tables_exist(tmp_path: Path) -> None:
    pdf = tmp_path / "sample-table.pdf"
    write_uncertain_text_table_pdf(pdf)
    epub = tmp_path / "book.epub"
    debug_dir = tmp_path / "debug"

    exit_code = main(["convert", str(pdf), "--out", str(epub), "--debug-dir", str(debug_dir)])

    assert exit_code == 0
    payload = json.loads((debug_dir / "table-fallbacks.json").read_text(encoding="utf-8"))
    assert payload["table_fallback_count"] == 1
    fallback = payload["table_fallbacks"][0]
    assert fallback["element_id"].startswith("table-")
    assert "Name Score Grade" in fallback["text"]
    assert fallback["confidence"] == 0.65
    assert fallback["warnings"][0]["code"] == "table_fallback_used"


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
