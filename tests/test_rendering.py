from __future__ import annotations

from pdf2epub_recovery.model import DocumentElement, DocumentIR
from pdf2epub_recovery.rendering.css import DEFAULT_CSS
from pdf2epub_recovery.rendering.xhtml import render_body_xhtml


def test_xhtml_includes_title_and_paragraph_classes() -> None:
    ir = DocumentIR(
        metadata={"title": "Readable Book"},
        elements=[
            DocumentElement(
                element_id="p0001",
                element_type="paragraph",
                text="A normal paragraph with enough words to be body text.",
            )
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert "<h1>Readable Book</h1>" in xhtml
    assert 'class="book"' in xhtml
    assert 'class="body-text"' in xhtml


def test_epub_css_is_reader_friendly() -> None:
    assert "font-size" not in DEFAULT_CSS.split("body", 1)[1].split("}", 1)[0]
    assert "line-height: 1.55" in DEFAULT_CSS
    assert "text-indent" in DEFAULT_CSS
    assert "max-width: 42em" in DEFAULT_CSS
