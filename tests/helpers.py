from __future__ import annotations

from pathlib import Path


def write_text_pdf(
    path: Path,
    pages: list[str],
    *,
    title: str = "Sample Book",
    header: str | None = None,
    page_numbers: bool = False,
    two_columns: bool = False,
) -> None:
    import fitz  # type: ignore[import-not-found]

    document = fitz.open()
    document.set_metadata({"title": title})
    for index, text in enumerate(pages):
        page = document.new_page(width=300, height=420)
        if header:
            page.insert_text((40, 32), header, fontsize=10)
        if two_columns:
            page.insert_textbox(fitz.Rect(35, 80, 135, 340), text, fontsize=10)
            page.insert_textbox(fitz.Rect(170, 80, 270, 340), f"Right {index + 1}", fontsize=10)
        else:
            page.insert_textbox(fitz.Rect(45, 80, 255, 340), text, fontsize=11)
        if page_numbers:
            page.insert_text((146, 392), str(index + 1), fontsize=10)
    document.save(path)
    document.close()
