"""PyMuPDF-backed raw PDF extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf2epub_recovery.model import (
    BBox,
    ExtractedDocument,
    ExtractedPage,
    QualityWarning,
    RawTextBlock,
)


class PyMuPDFExtractor:
    """Extract raw text blocks and geometry with PyMuPDF."""

    source_engine = "pymupdf"

    def extract(self, path: Path, max_pages: int | None = None) -> ExtractedDocument:
        try:
            import fitz  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - dependency is installed in tests
            raise RuntimeError("PyMuPDF is required for PDF extraction.") from exc

        warnings: list[QualityWarning] = []
        pages: list[ExtractedPage] = []

        try:
            with fitz.open(path) as document:
                metadata = _clean_metadata(document.metadata or {})
                limit = min(document.page_count, max_pages) if max_pages else document.page_count

                for page_index in range(limit):
                    page = document.load_page(page_index)
                    rect = page.rect
                    blocks: list[RawTextBlock] = []
                    image_count = 0

                    for raw in page.get_text("blocks"):
                        x0, y0, x1, y1, text, block_no, block_type = _parse_block(raw)
                        if block_type == 1:
                            image_count += 1
                            continue
                        if block_type != 0:
                            continue

                        normalized = _normalize_block_text(text)
                        if not normalized.strip():
                            continue

                        blocks.append(
                            RawTextBlock(
                                block_id=f"p{page_index + 1:04d}-b{len(blocks) + 1:04d}",
                                page_index=page_index,
                                page_width=float(rect.width),
                                page_height=float(rect.height),
                                raw_text=normalized,
                                bbox=BBox(float(x0), float(y0), float(x1), float(y1)),
                                source_engine=self.source_engine,
                                confidence=1.0,
                            )
                        )

                    page_warnings: list[QualityWarning] = []
                    if not blocks:
                        page_warnings.append(
                            QualityWarning(
                                code="page_has_no_native_text",
                                message="No native text blocks were extracted from this page.",
                                page_index=page_index,
                            )
                        )

                    pages.append(
                        ExtractedPage(
                            page_index=page_index,
                            width=float(rect.width),
                            height=float(rect.height),
                            text_blocks=blocks,
                            image_count=image_count,
                            warnings=page_warnings,
                        )
                    )

                if max_pages and max_pages < document.page_count:
                    warnings.append(
                        QualityWarning(
                            code="max_pages_applied",
                            severity="info",
                            message=f"Extraction limited to first {max_pages} pages.",
                        )
                    )

        except Exception as exc:
            raise RuntimeError(f"PyMuPDF could not extract PDF: {exc}") from exc

        return ExtractedDocument(
            input_path=str(path),
            source_engine=self.source_engine,
            metadata=metadata,
            pages=pages,
            warnings=warnings,
        )


def _parse_block(raw: tuple[Any, ...]) -> tuple[float, float, float, float, str, int, int]:
    x0, y0, x1, y1, text, block_no, *rest = raw
    block_type = int(rest[0]) if rest else 0
    return float(x0), float(y0), float(x1), float(y1), str(text), int(block_no), block_type


def _normalize_block_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value not in {None, ""}}
