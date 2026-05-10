"""PyMuPDF-backed raw PDF extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf2epub_recovery.model import (
    BBox,
    ExtractedDocument,
    ExtractedImage,
    ExtractedPage,
    QualityWarning,
    RawTextBlock,
)

_SUPPORTED_IMAGE_MEDIA_TYPES = {
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
}


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

                    for raw in page.get_text("blocks"):
                        x0, y0, x1, y1, text, _block_no, block_type = _parse_block(raw)
                        if block_type == 1:
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

                    images = _extract_page_images(
                        document=document,
                        page=page,
                        page_index=page_index,
                        page_width=float(rect.width),
                        page_height=float(rect.height),
                        source_engine=self.source_engine,
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
                    for image in images:
                        page_warnings.extend(image.warnings)

                    pages.append(
                        ExtractedPage(
                            page_index=page_index,
                            width=float(rect.width),
                            height=float(rect.height),
                            text_blocks=blocks,
                            images=images,
                            image_count=len(images),
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


def _extract_page_images(
    *,
    document: Any,
    page: Any,
    page_index: int,
    page_width: float,
    page_height: float,
    source_engine: str,
) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    image_entries = page.get_images(full=True)

    for entry in image_entries:
        xref = int(entry[0])
        smask = int(entry[1]) if len(entry) > 1 else 0
        rects = page.get_image_rects(xref) or [None]
        image_data = _extract_image_data(document, xref, smask)

        for rect in rects:
            image_index = len(images) + 1
            image_id = f"p{page_index + 1:04d}-img{image_index:04d}"
            warnings = list(image_data["warnings"])
            if rect is None:
                bbox = BBox(0.0, 0.0, 0.0, 0.0)
                warnings.append(
                    QualityWarning(
                        code="image_bbox_unavailable",
                        message="Image was detected, but its page position was unavailable.",
                        page_index=page_index,
                    )
                )
            else:
                bbox = BBox(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))

            images.append(
                ExtractedImage(
                    image_id=image_id,
                    page_index=page_index,
                    page_width=page_width,
                    page_height=page_height,
                    bbox=bbox,
                    source_engine=source_engine,
                    xref=xref,
                    extension=image_data["extension"],
                    media_type=image_data["media_type"],
                    data=image_data["data"],
                    pixel_width=image_data["pixel_width"],
                    pixel_height=image_data["pixel_height"],
                    confidence=0.85 if image_data["data"] else 0.4,
                    warnings=warnings,
                )
            )

    return images


def _extract_image_data(document: Any, xref: int, smask: int) -> dict[str, Any]:
    warnings: list[QualityWarning] = []
    if smask:
        warnings.append(
            QualityWarning(
                code="image_has_mask_not_preserved",
                message=(
                    "Image uses a mask or transparency that is not preserved "
                    "in this MVP slice."
                ),
            )
        )
        return {
            "data": None,
            "extension": None,
            "media_type": None,
            "pixel_width": None,
            "pixel_height": None,
            "warnings": warnings,
        }

    try:
        extracted = document.extract_image(xref)
    except Exception as exc:
        warnings.append(
            QualityWarning(
                code="image_extract_failed",
                message=f"PyMuPDF could not extract image bytes: {exc}",
            )
        )
        return {
            "data": None,
            "extension": None,
            "media_type": None,
            "pixel_width": None,
            "pixel_height": None,
            "warnings": warnings,
        }

    extension = str(extracted.get("ext") or "").lower()
    media_type = _SUPPORTED_IMAGE_MEDIA_TYPES.get(extension)
    data = extracted.get("image")
    if media_type is None or not isinstance(data, bytes) or not data:
        warnings.append(
            QualityWarning(
                code="image_format_not_preserved",
                message=(
                    "Image was detected, but its extracted format is not supported for "
                    "EPUB preservation in this MVP slice."
                ),
            )
        )
        data = None

    return {
        "data": data,
        "extension": extension or None,
        "media_type": media_type,
        "pixel_width": _optional_int(extracted.get("width")),
        "pixel_height": _optional_int(extracted.get("height")),
        "warnings": warnings,
    }


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value not in {None, ""}}
