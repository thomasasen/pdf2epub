from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from pdf2epub_recovery.model import (
    DocumentElement,
    DocumentImage,
    DocumentIR,
    DocumentTable,
    DocumentTocEntry,
)
from pdf2epub_recovery.rendering.css import DEFAULT_CSS
from pdf2epub_recovery.rendering.epub import render_epub
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
    assert "background-color: #1f4e79" in DEFAULT_CSS
    assert "color: #fff" in DEFAULT_CSS
    assert "background-color: #f5f8fb" in DEFAULT_CSS
    assert "ul.bullet-list" in DEFAULT_CSS
    assert "aside.callout" in DEFAULT_CSS
    assert "background-color: #eef5fb" in DEFAULT_CSS
    assert "nav.pdf-toc" in DEFAULT_CSS


def test_xhtml_renders_semantic_table_when_rows_are_available() -> None:
    ir = DocumentIR(
        metadata={"title": "Table Book"},
        elements=[
            DocumentElement(
                element_id="table-p0001-b0001",
                element_type="table",
                text="Name        Score\nAda         98",
                table=DocumentTable(
                    rows=[["Name", "Score"], ["Ada", "98"]],
                    source_format="multispace",
                ),
            )
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert '<figure class="table" id="table-p0001-b0001"><table>' in xhtml
    assert "<thead><tr><th>Name</th><th>Score</th></tr></thead>" in xhtml
    assert "<tbody><tr><td>Ada</td><td>98</td></tr></tbody>" in xhtml
    assert "<pre>" not in xhtml


def test_xhtml_groups_bullet_paragraphs_as_list_items() -> None:
    ir = DocumentIR(
        metadata={"title": "List Book"},
        elements=[
            DocumentElement(
                element_id="p0001",
                element_type="paragraph",
                text="Intro paragraph.",
            ),
            DocumentElement(
                element_id="p0002",
                element_type="paragraph",
                text="•Metrics: Ziel ist eine Reduktion der Abweichung.",
            ),
            DocumentElement(
                element_id="p0003",
                element_type="paragraph",
                text="•EB-Signal: Wenn der Business Case nachvollziehbar ist.",
            ),
            DocumentElement(
                element_id="p0004",
                element_type="paragraph",
                text="Closing paragraph.",
            ),
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert '<ul class="bullet-list">' in xhtml
    assert '<li id="p0002">Metrics: Ziel ist eine Reduktion der Abweichung.</li>' in xhtml
    assert '<li id="p0003">EB-Signal: Wenn der Business Case nachvollziehbar ist.</li>' in xhtml
    assert "\u2022Metrics" not in xhtml
    assert xhtml.index("</ul>") < xhtml.index("Closing paragraph.")


def test_xhtml_renders_highlighted_callout() -> None:
    ir = DocumentIR(
        metadata={"title": "Callout Book"},
        elements=[
            DocumentElement(
                element_id="c0001",
                element_type="callout",
                text="Win Strategy\n\nNovaFlow positioniert sich als Führungssystem.",
            )
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert '<aside class="callout" id="c0001">' in xhtml
    assert '<p class="callout-title">Win Strategy</p>' in xhtml
    assert "<p>NovaFlow positioniert sich als Führungssystem.</p>" in xhtml


def test_xhtml_renders_pdf_toc_without_dot_leaders() -> None:
    ir = DocumentIR(
        metadata={"title": "TOC Book"},
        elements=[
            DocumentElement(
                element_id="toc-p0001",
                element_type="toc",
                text="Inhaltsverzeichnis",
                toc_entries=[
                    DocumentTocEntry(
                        "1. First Chapter",
                        level=1,
                        page_label="6",
                        target_id="p0002",
                    ),
                    DocumentTocEntry("Nested Section", level=2, page_label="7"),
                ],
            )
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert '<nav class="pdf-toc" epub:type="toc">' in xhtml
    assert '<li class="toc-level-1"><a href="#p0002">1. First Chapter</a>' in xhtml
    assert '<span class="toc-page">6</span>' in xhtml
    assert 'class="toc-level-2"' in xhtml
    assert ". . ." not in xhtml


def test_xhtml_links_web_addresses_in_text_surfaces() -> None:
    ir = DocumentIR(
        metadata={"title": "Link Book"},
        elements=[
            DocumentElement(
                element_id="p0001",
                element_type="paragraph",
                text="Read https://example.com/docs.",
            ),
            DocumentElement(
                element_id="c0001",
                element_type="callout",
                text="Source\n\nSee http://example.org/path?q=1.",
            ),
            DocumentElement(
                element_id="t0001",
                element_type="table",
                text="Name | URL\nDocs | https://example.com/table",
            ),
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert '<a href="https://example.com/docs">https://example.com/docs</a>.' in xhtml
    assert '<a href="http://example.org/path?q=1">http://example.org/path?q=1</a>.' in xhtml
    assert '<a href="https://example.com/table">https://example.com/table</a>' in xhtml


def test_xhtml_keeps_preformatted_table_fallback_when_rows_are_uncertain() -> None:
    ir = DocumentIR(
        metadata={"title": "Fallback Book"},
        elements=[
            DocumentElement(
                element_id="table-p0001-b0001",
                element_type="table",
                text="Name Score\nAda         98",
            )
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert 'class="table-fallback"' in xhtml
    assert "<pre>Name Score\nAda         98</pre>" in xhtml


def test_xhtml_renders_pipe_table_fallback_as_visible_table() -> None:
    ir = DocumentIR(
        metadata={"title": "Fallback Table Book"},
        elements=[
            DocumentElement(
                element_id="table-p0001-b0001",
                element_type="table",
                text="Feld | Inhalt\nAnbieter | NovaFlow\nKunde | Auron",
            )
        ],
    )

    xhtml = render_body_xhtml(ir)

    assert '<figure class="table-fallback" id="table-p0001-b0001"><table>' in xhtml
    assert "<thead><tr><th>Feld</th><th>Inhalt</th></tr></thead>" in xhtml
    assert "<tbody><tr><td>Anbieter</td><td>NovaFlow</td></tr>" in xhtml
    assert "<pre>" not in xhtml


def test_render_epub_writes_minimal_epub_structure(tmp_path: Path) -> None:
    epub = tmp_path / "book.epub"
    ir = DocumentIR(
        metadata={"title": "Zip Book", "language": "en"},
        elements=[
            DocumentElement(
                element_id="p0001",
                element_type="paragraph",
                text="A paragraph in the generated EPUB.",
            ),
            DocumentElement(
                element_id="img0001",
                element_type="image",
                text="Image from page 1",
                image=DocumentImage(
                    image_id="img0001",
                    file_name="images/img0001.png",
                    media_type="image/png",
                    data=b"png-bytes",
                    alt_text="Image from page 1",
                    source_refs=[],
                ),
            ),
        ],
    )

    render_epub(ir, epub)

    with zipfile.ZipFile(epub) as archive:
        names = archive.namelist()
        assert names[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert "META-INF/container.xml" in names
        assert "EPUB/package.opf" in names
        assert "EPUB/toc.ncx" in names
        assert "EPUB/nav.xhtml" in names
        assert "EPUB/text/text.xhtml" in names
        assert "EPUB/styles/book.css" in names
        assert "EPUB/images/img0001.png" in names

        package = archive.read("EPUB/package.opf").decode("utf-8")
        ncx = archive.read("EPUB/toc.ncx").decode("utf-8")
        chapter = archive.read("EPUB/text/text.xhtml").decode("utf-8")

    ET.fromstring(chapter)
    assert 'id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"' in package
    assert '<spine toc="ncx">' in package
    assert '<content src="text/text.xhtml"/>' in ncx
    assert "A paragraph in the generated EPUB." in chapter
    assert '<img src="../images/img0001.png" alt="Image from page 1" />' in chapter


def test_render_epub_uses_resolved_pdf_toc_entries_for_nav_and_ncx(tmp_path: Path) -> None:
    epub = tmp_path / "book.epub"
    ir = DocumentIR(
        metadata={"title": "Linked Book", "language": "en"},
        elements=[
            DocumentElement(
                element_id="toc-p0001",
                element_type="toc",
                text="Contents",
                toc_entries=[
                    DocumentTocEntry("Chapter One", level=1, page_label="3", target_id="p0001"),
                    DocumentTocEntry("Unresolved", level=1, page_label="99"),
                ],
            ),
            DocumentElement(
                element_id="p0001",
                element_type="paragraph",
                text="Chapter One",
            ),
        ],
    )

    render_epub(ir, epub)

    with zipfile.ZipFile(epub) as archive:
        nav = archive.read("EPUB/nav.xhtml").decode("utf-8")
        ncx = archive.read("EPUB/toc.ncx").decode("utf-8")
        chapter = archive.read("EPUB/text/text.xhtml").decode("utf-8")

    assert '<a href="text/text.xhtml#p0001">Chapter One</a>' in nav
    assert "<span>Unresolved</span>" in nav
    assert '<content src="text/text.xhtml#p0001"/>' in ncx
    assert '<p class="short" id="p0001">Chapter One</p>' in chapter
