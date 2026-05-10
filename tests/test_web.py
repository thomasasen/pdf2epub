from __future__ import annotations

from pdf2epub_recovery.cli import build_parser
from pdf2epub_recovery.pipeline import convert_pdf_to_epub
from pdf2epub_recovery.web.server import APP_JS, INDEX_HTML, STYLE_CSS, _parse_multipart
from tests.helpers import write_text_pdf


def test_web_command_is_available() -> None:
    parser = build_parser()
    args = parser.parse_args(["web", "--host", "127.0.0.1", "--port", "0", "--no-browser"])

    assert args.command == "web"
    assert args.no_browser is True


def test_web_page_has_progress_and_log() -> None:
    assert "progress-bar" in INDEX_HTML
    assert 'id="log"' in INDEX_HTML
    assert "EPUB erstellen" in INDEX_HTML


def test_web_page_explains_options_and_supports_drag_drop() -> None:
    assert "Seitenreste behalten" in INDEX_HTML
    assert "Worttrennung nicht reparieren" in INDEX_HTML
    assert "Konvertiert nur die ersten Seiten" in INDEX_HTML
    assert "dragover" in APP_JS
    assert "DataTransfer" in APP_JS
    assert ".dropzone.is-dragging" in STYLE_CSS


def test_multipart_parser_reads_pdf_and_options() -> None:
    boundary = "----test-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="keep_artifacts"\r\n\r\n'
            "on\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="pdf"; filename="book.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + b"%PDF-1.7\n%%EOF\r\n"
        + f"--{boundary}--\r\n".encode()
    )

    fields, files = _parse_multipart(f"multipart/form-data; boundary={boundary}", body)

    assert fields["keep_artifacts"] == "on"
    assert files["pdf"]["filename"] == "book.pdf"
    assert files["pdf"]["content"].startswith(b"%PDF")


def test_pipeline_progress_callback_reports_stages(tmp_path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(pdf, ["Progress test page."])
    messages: list[tuple[int, str]] = []

    convert_pdf_to_epub(
        pdf,
        tmp_path / "book.epub",
        progress_callback=lambda percent, message: messages.append((percent, message)),
    )

    assert messages[0][0] == 5
    assert messages[-1] == (100, "Done.")
    assert any("Writing EPUB" in message for _percent, message in messages)
