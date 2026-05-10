from __future__ import annotations

from pathlib import Path

_RED_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


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


def write_text_and_image_pdf(path: Path) -> None:
    import fitz  # type: ignore[import-not-found]

    document = fitz.open()
    document.set_metadata({"title": "Image Sample"})
    page = document.new_page(width=300, height=420)
    page.insert_textbox(
        fitz.Rect(45, 60, 255, 120),
        "Text before the embedded image.",
        fontsize=11,
    )
    page.insert_image(fitz.Rect(90, 145, 210, 245), stream=_RED_PNG)
    page.insert_textbox(
        fitz.Rect(45, 270, 255, 340),
        "Text after the embedded image.",
        fontsize=11,
    )
    document.save(path)
    document.close()


def write_text_table_pdf(path: Path) -> None:
    import fitz  # type: ignore[import-not-found]

    document = fitz.open()
    document.set_metadata({"title": "Table Sample"})
    page = document.new_page(width=360, height=420)
    page.insert_textbox(
        fitz.Rect(45, 55, 315, 95),
        "Text before the table.",
        fontsize=11,
    )
    page.insert_text(
        (55, 135),
        "Name        Score       Grade\nAda         98          A\nGrace       91          A",
        fontsize=10,
        fontname="cour",
    )
    page.insert_textbox(
        fitz.Rect(45, 250, 315, 330),
        "Text after the table.",
        fontsize=11,
    )
    document.save(path)
    document.close()
