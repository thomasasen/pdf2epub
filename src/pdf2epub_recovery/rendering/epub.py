"""EPUB rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from pdf2epub_recovery.model import DocumentImage, DocumentIR, DocumentTocEntry
from pdf2epub_recovery.rendering.css import DEFAULT_CSS
from pdf2epub_recovery.rendering.xhtml import render_body_xhtml


def render_epub(ir: DocumentIR, output_path: Path) -> None:
    """Write a basic reflowable EPUB."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = str(ir.metadata.get("title") or output_path.stem or "Recovered Document")
    language = str(ir.metadata.get("language") or "en")
    identifier = f"urn:uuid:{uuid4()}"
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    images = _document_images(ir)
    toc_entries = _document_toc_entries(ir)

    with ZipFile(output_path, "w") as archive:
        mimetype = ZipInfo("mimetype")
        mimetype.compress_type = ZIP_STORED
        archive.writestr(mimetype, "application/epub+zip")
        archive.writestr("META-INF/container.xml", _container_xml(), compress_type=ZIP_DEFLATED)
        archive.writestr(
            "EPUB/package.opf",
            _package_opf(title, language, identifier, modified, images),
            compress_type=ZIP_DEFLATED,
        )
        archive.writestr(
            "EPUB/toc.ncx",
            _toc_ncx(title, identifier, toc_entries),
            compress_type=ZIP_DEFLATED,
        )
        archive.writestr(
            "EPUB/nav.xhtml",
            _nav_xhtml(title, language, toc_entries),
            compress_type=ZIP_DEFLATED,
        )
        archive.writestr(
            "EPUB/text/text.xhtml",
            _chapter_xhtml(ir, title, language),
            compress_type=ZIP_DEFLATED,
        )
        archive.writestr(
            "EPUB/styles/book.css",
            DEFAULT_CSS.encode("utf-8"),
            compress_type=ZIP_DEFLATED,
        )
        for image in images:
            archive.writestr(f"EPUB/{image.file_name}", image.data, compress_type=ZIP_DEFLATED)


def _document_images(ir: DocumentIR) -> list[DocumentImage]:
    images: list[DocumentImage] = []
    seen: set[str] = set()
    for element in ir.elements:
        if element.element_type != "image" or element.image is None:
            continue
        if element.image.file_name in seen:
            continue
        images.append(element.image)
        seen.add(element.image.file_name)
    return images


def _document_toc_entries(ir: DocumentIR) -> list[DocumentTocEntry]:
    for element in ir.elements:
        if element.element_type == "toc" and element.toc_entries:
            return element.toc_entries
    return []


def _container_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _package_opf(
    title: str,
    language: str,
    identifier: str,
    modified: str,
    images: list[DocumentImage],
) -> str:
    manifest_images = "\n".join(
        f'    <item id="{_xml_attr(_manifest_id(image.image_id))}" '
        f'href="{_xml_attr(image.file_name)}" '
        f'media-type="{_xml_attr(image.media_type)}"/>'
        for image in images
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package version="3.0"
         unique-identifier="book-id"
         xmlns="http://www.idpf.org/2007/opf"
         prefix="dcterms: http://purl.org/dc/terms/">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{_xml_text(identifier)}</dc:identifier>
    <dc:title>{_xml_text(title)}</dc:title>
    <dc:language>{_xml_text(language)}</dc:language>
    <meta property="dcterms:modified">{_xml_text(modified)}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="text" href="text/text.xhtml" media-type="application/xhtml+xml"/>
    <item id="css" href="styles/book.css" media-type="text/css"/>
{manifest_images}
  </manifest>
  <spine toc="ncx">
    <itemref idref="text"/>
  </spine>
</package>
"""


def _toc_ncx(title: str, identifier: str, toc_entries: list[DocumentTocEntry]) -> str:
    nav_points = _ncx_nav_points(title, toc_entries)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{_xml_attr(identifier)}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{_xml_text(title)}</text>
  </docTitle>
  <navMap>
{nav_points}
  </navMap>
</ncx>
"""


def _nav_xhtml(title: str, language: str, toc_entries: list[DocumentTocEntry]) -> str:
    language_attr = _xml_attr(language)
    nav_items = _nav_items(title, toc_entries)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      lang="{language_attr}"
      xml:lang="{language_attr}">
<head>
  <title>{_xml_text(title)}</title>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{_xml_text(title)}</h1>
    <ol>
{nav_items}
    </ol>
  </nav>
</body>
</html>
"""


def _chapter_xhtml(ir: DocumentIR, title: str, language: str) -> str:
    language_attr = _xml_attr(language)
    body = render_body_xhtml(ir, image_prefix="../")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      lang="{language_attr}"
      xml:lang="{language_attr}">
<head>
  <title>{_xml_text(title)}</title>
  <link rel="stylesheet" type="text/css" href="../styles/book.css"/>
</head>
<body>
{body}
</body>
</html>
"""


def _manifest_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)


def _xml_text(value: str) -> str:
    return escape(value, quote=False)


def _xml_attr(value: str) -> str:
    return escape(value, quote=True)


def _target_href(target_id: str | None) -> str:
    if not target_id:
        return "text/text.xhtml"
    return f"text/text.xhtml#{target_id}"


def _ncx_nav_points(title: str, toc_entries: list[DocumentTocEntry]) -> str:
    linked_entries = [entry for entry in toc_entries if entry.target_id]
    if not linked_entries:
        return f"""    <navPoint id="navpoint-1" playOrder="1">
      <navLabel>
        <text>{_xml_text(title)}</text>
      </navLabel>
      <content src="text/text.xhtml"/>
    </navPoint>"""

    points: list[str] = []
    for index, entry in enumerate(linked_entries, start=1):
        points.append(
            f"""    <navPoint id="navpoint-{index}" playOrder="{index}">
      <navLabel>
        <text>{_xml_text(entry.title)}</text>
      </navLabel>
      <content src="{_xml_attr(_target_href(entry.target_id))}"/>
    </navPoint>"""
        )
    return "\n".join(points)


def _nav_items(title: str, toc_entries: list[DocumentTocEntry]) -> str:
    if not toc_entries:
        return f'      <li><a href="text/text.xhtml">{_xml_text(title)}</a></li>'

    items: list[str] = []
    for entry in toc_entries:
        css_class = f"toc-level-{max(1, min(6, entry.level))}"
        if entry.target_id:
            label = (
                f'<a href="{_xml_attr(_target_href(entry.target_id))}">'
                f"{_xml_text(entry.title)}</a>"
            )
        else:
            label = f"<span>{_xml_text(entry.title)}</span>"
        items.append(f'      <li class="{css_class}">{label}</li>')
    return "\n".join(items)
