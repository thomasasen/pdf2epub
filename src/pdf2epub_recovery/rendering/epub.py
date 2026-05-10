"""EPUB rendering."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pdf2epub_recovery.model import DocumentIR
from pdf2epub_recovery.rendering.css import DEFAULT_CSS
from pdf2epub_recovery.rendering.xhtml import render_body_xhtml


def render_epub(ir: DocumentIR, output_path: Path) -> None:
    """Write a basic reflowable EPUB."""

    try:
        from ebooklib import epub  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency is installed in tests
        raise RuntimeError("EbookLib is required for EPUB rendering.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = str(ir.metadata.get("title") or output_path.stem or "Recovered Document")
    language = str(ir.metadata.get("language") or "en")

    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid4()}")
    book.set_title(title)
    book.set_language(language)

    chapter = epub.EpubHtml(title=title, file_name="text.xhtml", lang=language)
    chapter.content = render_body_xhtml(ir)

    css = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=DEFAULT_CSS.encode("utf-8"),
    )
    chapter.add_item(css)

    book.add_item(chapter)
    book.add_item(css)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.toc = (epub.Link("text.xhtml", title, "text"),)
    book.spine = ["nav", chapter]

    epub.write_epub(str(output_path), book, {})
