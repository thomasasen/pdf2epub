from __future__ import annotations

from pathlib import Path

from pdf2epub_recovery.extraction.pymupdf_extractor import PyMuPDFExtractor
from tests.helpers import write_text_pdf


def test_extraction_preserves_page_and_bbox(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(pdf, ["Extract this native text."])

    extracted = PyMuPDFExtractor().extract(pdf)

    assert extracted.source_engine == "pymupdf"
    assert extracted.pages[0].page_index == 0
    block = extracted.pages[0].text_blocks[0]
    assert "Extract this" in block.raw_text
    assert block.page_index == 0
    assert block.bbox.x1 > block.bbox.x0
    assert block.source_ref().engine == "pymupdf"
