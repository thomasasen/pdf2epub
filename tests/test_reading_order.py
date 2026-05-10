from __future__ import annotations

from pdf2epub_recovery.model import BBox, RawTextBlock
from pdf2epub_recovery.reading_order.resolver import resolve_reading_order


def block(block_id: str, text: str, x0: float, y0: float) -> RawTextBlock:
    return RawTextBlock(
        block_id=block_id,
        page_index=0,
        page_width=300,
        page_height=400,
        raw_text=text,
        bbox=BBox(x0, y0, x0 + 80, y0 + 20),
        source_engine="test",
    )


def column_block(block_id: str, text: str, x0: float, y0: float) -> RawTextBlock:
    return RawTextBlock(
        block_id=block_id,
        page_index=0,
        page_width=300,
        page_height=400,
        raw_text=text,
        bbox=BBox(x0, y0, x0 + 70, y0 + 20),
        source_engine="test",
    )


def test_one_column_orders_top_to_bottom_then_left_to_right() -> None:
    blocks = [
        block("b3", "third", 80, 150),
        block("b1", "first", 40, 90),
        block("b2", "second", 45, 120),
    ]

    result = resolve_reading_order(blocks, "one_column")

    assert [item.raw_text for item in result.blocks] == ["first", "second", "third"]
    assert not result.warnings


def test_possible_multi_column_adds_warning() -> None:
    result = resolve_reading_order([block("b1", "first", 40, 90)], "possible_multi_column")

    assert result.warnings[0].code == "possible_multi_column_reading_order_uncertain"


def test_possible_multi_column_orders_left_column_before_right_column() -> None:
    blocks = [
        column_block("r1", "right top", 190, 90),
        column_block("l2", "left bottom", 35, 130),
        column_block("r2", "right bottom", 190, 130),
        column_block("l1", "left top", 35, 90),
    ]

    result = resolve_reading_order(blocks, "possible_multi_column")

    assert [item.raw_text for item in result.blocks] == [
        "left top",
        "left bottom",
        "right top",
        "right bottom",
    ]
