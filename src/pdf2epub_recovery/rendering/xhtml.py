"""XHTML rendering helpers."""

from __future__ import annotations

from html import escape

from pdf2epub_recovery.model import DocumentIR


def render_body_xhtml(ir: DocumentIR) -> str:
    """Render the IR body as simple semantic XHTML."""

    title = escape(str(ir.metadata.get("title") or "Recovered Document"), quote=False)
    parts = [f'<section class="book"><h1>{title}</h1>']
    for element in ir.elements:
        if element.element_type == "paragraph":
            css_class = "short" if _looks_like_short_standalone_text(element.text) else "body-text"
            parts.append(f'<p class="{css_class}">{escape(element.text, quote=False)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def _looks_like_short_standalone_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 90:
        return False
    if len(stripped.split()) > 10:
        return False
    return not stripped.endswith((".", ",", ";", ":"))
