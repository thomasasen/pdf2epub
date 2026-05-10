"""XHTML rendering helpers."""

from __future__ import annotations

import re
from html import escape

from pdf2epub_recovery.model import DocumentElement, DocumentIR, DocumentTable

_URL_RE = re.compile(r"https?://[^\s<>'\"]+")
_TRAILING_URL_PUNCTUATION = ".,;:!?)\"]}"


def render_body_xhtml(ir: DocumentIR, *, image_prefix: str = "") -> str:
    """Render the IR body as simple semantic XHTML."""

    title = escape(str(ir.metadata.get("title") or "Recovered Document"), quote=False)
    parts = [f'<section class="book"><h1>{title}</h1>']
    list_open = False
    for element in ir.elements:
        if element.element_type == "paragraph":
            if _is_bullet_text(element.text):
                if not list_open:
                    parts.append('<ul class="bullet-list">')
                    list_open = True
                parts.append(f"<li>{_render_inline_text(_strip_bullet_marker(element.text))}</li>")
                continue

            if list_open:
                parts.append("</ul>")
                list_open = False
            css_class = "short" if _looks_like_short_standalone_text(element.text) else "body-text"
            parts.append(f'<p class="{css_class}">{_render_inline_text(element.text)}</p>')
        elif element.element_type == "image" and element.image:
            if list_open:
                parts.append("</ul>")
                list_open = False
            src = escape(f"{image_prefix}{element.image.file_name}", quote=True)
            alt = escape(element.image.alt_text, quote=True)
            parts.append(
                f'<figure class="image"><img src="{src}" alt="{alt}" /></figure>'
            )
        elif element.element_type == "callout":
            if list_open:
                parts.append("</ul>")
                list_open = False
            parts.append(_render_callout(element.text))
        elif element.element_type == "toc":
            if list_open:
                parts.append("</ul>")
                list_open = False
            parts.append(_render_toc(element))
        elif element.element_type == "table":
            if list_open:
                parts.append("</ul>")
                list_open = False
            parts.append(_render_table(element))
    if list_open:
        parts.append("</ul>")
    parts.append("</section>")
    return "\n".join(parts)


def _looks_like_short_standalone_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 90:
        return False
    if len(stripped.split()) > 10:
        return False
    return not stripped.endswith((".", ",", ";", ":"))


def _is_bullet_text(text: str) -> bool:
    return text.lstrip().startswith("\u2022")


def _strip_bullet_marker(text: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("\u2022"):
        return stripped[1:].lstrip()
    return stripped


def _render_callout(text: str) -> str:
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not parts:
        return '<aside class="callout"></aside>'

    rendered = ['<aside class="callout">']
    first, *rest = parts
    if _looks_like_short_standalone_text(first):
        rendered.append(f'<p class="callout-title">{_render_inline_text(first)}</p>')
    else:
        rendered.append(f"<p>{_render_inline_text(first)}</p>")

    for part in rest:
        rendered.append(f"<p>{_render_inline_text(part)}</p>")
    rendered.append("</aside>")
    return "".join(rendered)


def _render_toc(element: DocumentElement) -> str:
    title = escape(element.text or "Inhaltsverzeichnis", quote=False)
    parts = [f'<nav class="pdf-toc" epub:type="toc"><h2>{title}</h2><ol>']
    for entry in element.toc_entries:
        css_class = f"toc-level-{max(1, min(6, entry.level))}"
        entry_title = escape(entry.title, quote=False)
        page = escape(entry.page_label or "", quote=False)
        page_span = f'<span class="toc-page">{page}</span>' if page else ""
        parts.append(f'<li class="{css_class}"><span>{entry_title}</span>{page_span}</li>')
    parts.append("</ol></nav>")
    return "".join(parts)


def _render_table(element: DocumentElement) -> str:
    if element.table is None:
        return _render_table_fallback(element.text)
    return _render_semantic_table(element.table)


def _render_table_fallback(text: str) -> str:
    rows = _pipe_rows(text)
    if rows:
        parts = ['<figure class="table-fallback"><table>']
        header = rows[0]
        parts.append(
            "<thead><tr>"
            + "".join(f"<th>{_render_inline_text(cell)}</th>" for cell in header)
            + "</tr></thead>"
        )
        body_rows = rows[1:]
        if body_rows:
            parts.append("<tbody>")
            for row in body_rows:
                parts.append(
                    "<tr>"
                    + "".join(f"<td>{_render_inline_text(cell)}</td>" for cell in row)
                    + "</tr>"
                )
            parts.append("</tbody>")
        parts.append("</table></figure>")
        return "".join(parts)

    return (
        '<figure class="table-fallback">'
        f"<pre>{escape(text, quote=False)}</pre>"
        "</figure>"
    )


def _pipe_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if "|" not in line:
            return []
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 2 or any(not cell for cell in cells):
            return []
        rows.append(cells)
    if len(rows) < 2:
        return []
    return rows


def _render_semantic_table(table: DocumentTable) -> str:
    rows = table.rows
    if not rows:
        return '<figure class="table-fallback"><pre></pre></figure>'

    parts = ['<figure class="table"><table>']
    body_rows = rows
    if table.header_row:
        header = rows[0]
        parts.append(
            "<thead><tr>"
            + "".join(f"<th>{_render_inline_text(cell)}</th>" for cell in header)
            + "</tr></thead>"
        )
        body_rows = rows[1:]

    if body_rows:
        parts.append("<tbody>")
        for row in body_rows:
            parts.append(
                "<tr>"
                + "".join(f"<td>{_render_inline_text(cell)}</td>" for cell in row)
                + "</tr>"
            )
        parts.append("</tbody>")

    parts.append("</table></figure>")
    return "".join(parts)


def _render_inline_text(text: str) -> str:
    rendered: list[str] = []
    position = 0
    for match in _URL_RE.finditer(text):
        rendered.append(escape(text[position : match.start()], quote=False))
        url, trailing = _split_trailing_url_punctuation(match.group(0))
        href = escape(url, quote=True)
        label = escape(url, quote=False)
        rendered.append(f'<a href="{href}">{label}</a>')
        rendered.append(escape(trailing, quote=False))
        position = match.end()
    rendered.append(escape(text[position:], quote=False))
    return "".join(rendered)


def _split_trailing_url_punctuation(url: str) -> tuple[str, str]:
    trailing = ""
    while url and url[-1] in _TRAILING_URL_PUNCTUATION:
        trailing = url[-1] + trailing
        url = url[:-1]
    return url, trailing
