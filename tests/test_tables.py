from __future__ import annotations

from pdf2epub_recovery.model import BBox, RawTextBlock
from pdf2epub_recovery.structure.tables import detect_table_like_blocks


def block(text: str) -> RawTextBlock:
    return RawTextBlock(
        block_id="p0001-b0001",
        page_index=0,
        page_width=300,
        page_height=400,
        raw_text=text,
        bbox=BBox(40, 100, 260, 160),
        source_engine="test",
    )


def test_detects_obvious_table_like_text_block() -> None:
    result = detect_table_like_blocks(
        [
            block(
                "Name        Score       Grade\n"
                "Ada         98          A\n"
                "Grace       91          A"
            )
        ]
    )

    assert len(result.table_blocks) == 1
    assert result.text_blocks == []
    assert result.table_elements[0].element_type == "table"
    assert result.warnings[0].code == "table_fallback_used"


def test_plain_wrapped_text_is_not_table_like() -> None:
    result = detect_table_like_blocks(
        [block("This is a normal paragraph\nthat merely wraps onto another line.")]
    )

    assert result.table_blocks == []
    assert len(result.text_blocks) == 1
    assert result.table_elements == []
