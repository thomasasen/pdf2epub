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
                message=(
                    "Possible multi-column page; reading order uses a conservative "
                    "column-aware fallback when columns are clear."
                ),
                page_index=page_index,
            )
            for page_index in pages
        )
        return ReadingOrderResult(
            blocks=[
                block
                for page_index in pages
                for block in _order_possible_multi_column_page(
                    [block for block in blocks if block.page_index == page_index]
                )
            ],
            warnings=warnings,
        )

    return ReadingOrderResult(
        blocks=sorted(blocks, key=_top_to_bottom_key),
        warnings=warnings,
    )


def _order_possible_multi_column_page(blocks: list[RawTextBlock]) -> list[RawTextBlock]:
    if not blocks:
        return []

    split = _clear_column_split(blocks)
    if split is None:
        return sorted(blocks, key=_top_to_bottom_key)

    left_blocks, right_blocks, other_blocks = split
    ordered_columns = [
        *sorted(left_blocks, key=_top_to_bottom_key),
        *sorted(right_blocks, key=_top_to_bottom_key),
    ]

    if not other_blocks:
        return ordered_columns

    column_top = _column_top(ordered_columns)
    column_bottom = _column_bottom(ordered_columns)
    before_columns = [block for block in other_blocks if block.bbox.y1 <= column_top]
    after_columns = [block for block in other_blocks if block.bbox.y0 >= column_bottom]
    middle = [
        block
        for block in other_blocks
        if block not in before_columns and block not in after_columns
    ]
    if middle:
        return sorted(blocks, key=_top_to_bottom_key)

    return [
        *sorted(before_columns, key=_top_to_bottom_key),
        *ordered_columns,
        *sorted(after_columns, key=_top_to_bottom_key),
    ]


def _clear_column_split(
    blocks: list[RawTextBlock],
) -> tuple[list[RawTextBlock], list[RawTextBlock], list[RawTextBlock]] | None:
    page_width = max(block.page_width for block in blocks)
    left_blocks = [block for block in blocks if _center_ratio(block, page_width) < 0.45]
    right_blocks = [block for block in blocks if _center_ratio(block, page_width) > 0.55]
    other_blocks = [
        block for block in blocks if block not in left_blocks and block not in right_blocks
    ]

    if not left_blocks or not right_blocks:
        return None

    left_edge = max(block.bbox.x1 for block in left_blocks)
    right_edge = min(block.bbox.x0 for block in right_blocks)
    if right_edge - left_edge < max(24.0, page_width * 0.08):
        return None

    if any(block.bbox.width > page_width * 0.62 for block in [*left_blocks, *right_blocks]):
        return None

    if not any(
        _vertical_overlap(left, right) >= 8.0 for left in left_blocks for right in right_blocks
    ):
        return None

    return left_blocks, right_blocks, other_blocks


def _top_to_bottom_key(block: RawTextBlock) -> tuple[int, float, float, str]:
    return (
        block.page_index,
        round(block.bbox.y0, 1),
        round(block.bbox.x0, 1),
        block.block_id,
    )


def _center_ratio(block: RawTextBlock, page_width: float) -> float:
    return ((block.bbox.x0 + block.bbox.x1) / 2.0) / page_width


def _vertical_overlap(left: RawTextBlock, right: RawTextBlock) -> float:
    return max(0.0, min(left.bbox.y1, right.bbox.y1) - max(left.bbox.y0, right.bbox.y0))


def _column_top(blocks: list[RawTextBlock]) -> float:
    return min(block.bbox.y0 for block in blocks)


def _column_bottom(blocks: list[RawTextBlock]) -> float:
    return max(block.bbox.y1 for block in blocks)
