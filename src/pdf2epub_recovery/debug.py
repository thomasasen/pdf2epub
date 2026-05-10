"""Debug JSON payloads for inspecting conversion decisions."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from pdf2epub_recovery.model import (
    DocumentElement,
    DocumentImage,
    ExtractedDocument,
    ExtractedImage,
    RawTextBlock,
    RemovedArtifact,
    SourceRef,
    json_ready,
)

if TYPE_CHECKING:
    from pdf2epub_recovery.pipeline import ConversionResult


def build_debug_payloads(result: ConversionResult) -> dict[str, dict[str, Any]]:
    """Return deterministic debug JSON payloads for a completed conversion."""

    payloads = {
        "removed-artifacts.json": removed_artifacts_payload(result.ir.removed_artifacts),
        "ordered-blocks.json": ordered_blocks_payload(result.ordered_blocks),
        "kept-margin-blocks.json": kept_margin_blocks_payload(
            result.ordered_blocks,
            keep_artifacts=result.keep_artifacts,
        ),
    }
    table_payload = table_fallbacks_payload(result.ir.elements)
    if table_payload["table_fallbacks"]:
        payloads["table-fallbacks.json"] = table_payload
    image_payload = images_payload(result.extracted, result.ir.elements)
    if image_payload["image_count"]:
        payloads["images.json"] = image_payload
    return payloads


def removed_artifacts_payload(artifacts: list[RemovedArtifact]) -> dict[str, Any]:
    sorted_artifacts = sorted(
        artifacts,
        key=lambda artifact: (
            artifact.source_ref.page_index,
            round(artifact.source_ref.bbox.y0, 3),
            round(artifact.source_ref.bbox.x0, 3),
            artifact.artifact_id,
        ),
    )
    counts = Counter(artifact.artifact_type for artifact in sorted_artifacts)
    return {
        "artifact_count": len(sorted_artifacts),
        "counts_by_type": dict(sorted(counts.items())),
        "removed_artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact.artifact_type,
                "page_index": artifact.source_ref.page_index,
                "block_id": artifact.source_ref.block_id,
                "bbox": json_ready(artifact.source_ref.bbox),
                "text": artifact.text,
                "reason": artifact.reason,
                "confidence": artifact.confidence,
                "source_engine": artifact.source_ref.engine,
            }
            for artifact in sorted_artifacts
        ],
    }


def ordered_blocks_payload(blocks: list[RawTextBlock]) -> dict[str, Any]:
    sorted_blocks = sorted(blocks, key=_block_sort_key)
    return {
        "block_count": len(sorted_blocks),
        "ordered_blocks": [
            _block_summary(block, order_index)
            for order_index, block in enumerate(sorted_blocks)
        ],
    }


def kept_margin_blocks_payload(
    blocks: list[RawTextBlock], *, keep_artifacts: bool = False
) -> dict[str, Any]:
    margin_blocks = [block for block in sorted(blocks, key=_block_sort_key) if _margin_zone(block)]
    return {
        "block_count": len(margin_blocks),
        "kept_margin_blocks": [
            {
                **_block_summary(block, order_index),
                "margin_zone": _margin_zone(block),
                "candidate_reason": _candidate_reason(block),
                "kept_reason": _kept_reason(keep_artifacts),
            }
            for order_index, block in enumerate(margin_blocks)
        ],
    }


def table_fallbacks_payload(elements: list[DocumentElement]) -> dict[str, Any]:
    table_elements = sorted(
        (
            element
            for element in elements
            if element.element_type == "table" and element.table is None
        ),
        key=_element_sort_key,
    )
    return {
        "table_fallback_count": len(table_elements),
        "table_fallbacks": [
            {
                "element_id": element.element_id,
                "source_refs": [_source_ref_summary(ref) for ref in element.source_refs],
                "text": element.text,
                "confidence": element.confidence,
                "warnings": [warning.to_dict() for warning in element.warnings],
            }
            for element in table_elements
        ],
    }


def images_payload(
    extracted: ExtractedDocument, elements: list[DocumentElement]
) -> dict[str, Any]:
    images = sorted(
        (image for page in extracted.pages for image in page.images),
        key=_image_sort_key,
    )
    preserved_images = {
        element.image.image_id: element.image
        for element in elements
        if element.element_type == "image" and element.image is not None
    }
    return {
        "image_count": len(images),
        "images": [
            _image_debug_summary(image, preserved_images.get(image.image_id))
            for image in images
        ],
    }


def _block_summary(block: RawTextBlock, order_index: int) -> dict[str, Any]:
    text = _normalized_text(block.raw_text)
    return {
        "order_index": order_index,
        "page_index": block.page_index,
        "block_id": block.block_id,
        "bbox": json_ready(block.bbox),
        "text_snippet": _snippet(text),
        "text": text,
        "source_engine": block.source_engine,
        "confidence": block.confidence,
        "warnings": [warning.to_dict() for warning in block.warnings],
    }


def _source_ref_summary(ref: SourceRef) -> dict[str, Any]:
    return {
        "page_index": ref.page_index,
        "block_id": ref.block_id,
        "bbox": json_ready(ref.bbox),
        "source_engine": ref.engine,
    }


def _image_debug_summary(
    image: ExtractedImage, preserved_image: DocumentImage | None
) -> dict[str, Any]:
    status = "preserved" if preserved_image is not None else "not_preserved"
    return {
        "image_id": image.image_id,
        "page_index": image.page_index,
        "placement": {
            "page_width": image.page_width,
            "page_height": image.page_height,
            "bbox": json_ready(image.bbox),
        },
        "provenance": {
            "source_engine": image.source_engine,
            "xref": image.xref,
        },
        "preservation": {
            "status": status,
            "file_name": preserved_image.file_name if preserved_image else None,
            "media_type": preserved_image.media_type if preserved_image else image.media_type,
            "extension": image.extension,
            "byte_count": len(image.data) if image.data else 0,
            "pixel_width": image.pixel_width,
            "pixel_height": image.pixel_height,
            "confidence": image.confidence,
            "warnings": [warning.to_dict() for warning in image.warnings],
        },
    }


def _block_sort_key(block: RawTextBlock) -> tuple[int, float, float, str]:
    return (
        block.page_index,
        round(block.bbox.y0, 3),
        round(block.bbox.x0, 3),
        block.block_id,
    )


def _image_sort_key(image: ExtractedImage) -> tuple[int, float, float, str]:
    return (
        image.page_index,
        round(image.bbox.y0, 3),
        round(image.bbox.x0, 3),
        image.image_id,
    )


def _element_sort_key(element: DocumentElement) -> tuple[int, float, float, str]:
    if not element.source_refs:
        return (10**9, 0.0, 0.0, element.element_id)
    ref = element.source_refs[0]
    return (
        ref.page_index,
        round(ref.bbox.y0, 3),
        round(ref.bbox.x0, 3),
        element.element_id,
    )


def _margin_zone(block: RawTextBlock) -> str | None:
    top_limit = block.page_height * 0.12
    bottom_limit = block.page_height * 0.88
    if block.bbox.y1 <= top_limit:
        return "top"
    if block.bbox.y0 >= bottom_limit:
        return "bottom"
    return None


def _candidate_reason(block: RawTextBlock) -> str:
    zone = _margin_zone(block)
    text = _normalized_text(block.raw_text)
    if text.isdigit():
        return f"Numeric text in the {zone} margin."
    return f"Text block in the {zone} margin."


def _kept_reason(keep_artifacts: bool) -> str:
    if keep_artifacts:
        return "Artifact cleanup was disabled by --keep-artifacts."
    return "Conservative cleanup did not classify this block as a removable page artifact."


def _normalized_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _snippet(text: str, limit: int = 160) -> str:
    one_line = " ".join(part.strip() for part in text.splitlines() if part.strip())
    if len(one_line) <= limit:
        return one_line
    return f"{one_line[: limit - 1]}..."
