"""Simple reading-order resolver."""

from __future__ import annotations

from dataclasses import dataclass, field

from pdf2epub_recovery.model import LayoutEstimate, QualityWarning, RawTextBlock


@dataclass(frozen=True)
class ReadingOrderResult:
    blocks: list[RawTextBlock]
    warnings: list[QualityWarning] = field(default_factory=list)


def resolve_reading_order(
    blocks: list[RawTextBlock], likely_layout: LayoutEstimate
) -> ReadingOrderResult:
    """Order blocks conservatively for the MVP."""

    warnings: list[QualityWarning] = []
    if likely_layout == "possible_multi_column":
        pages = sorted({block.page_index for block in blocks})
        warnings.extend(
            QualityWarning(
                code="possible_multi_column_reading_order_uncertain",
                message="Possible multi-column page; reading order is a conservative fallback.",
                page_index=page_index,
            )
            for page_index in pages
        )

    return ReadingOrderResult(
        blocks=sorted(
            blocks,
            key=lambda block: (
                block.page_index,
                round(block.bbox.y0, 1),
                round(block.bbox.x0, 1),
                block.block_id,
            ),
        ),
        warnings=warnings,
    )
