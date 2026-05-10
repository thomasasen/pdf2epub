from __future__ import annotations

from pdf2epub_recovery.model import BBox, RawTextBlock
from pdf2epub_recovery.structure.paragraphs import reconstruct_paragraphs


def block(block_id: str, text: str, y0: float = 100, y1: float = 130) -> RawTextBlock:
    return RawTextBlock(
        block_id=block_id,
        page_index=0,
        page_width=300,
        page_height=400,
        raw_text=text,
        bbox=BBox(40, y0, 260, y1),
        source_engine="test",
    )


def test_hard_line_wraps_become_readable_paragraph() -> None:
    result = reconstruct_paragraphs([block("b1", "This line wraps\ninside one paragraph.")])

    assert result.paragraphs[0].text == "This line wraps inside one paragraph."
    assert result.line_wrap_repairs == 1


def test_blank_lines_inside_block_preserve_paragraph_breaks() -> None:
    result = reconstruct_paragraphs([block("b1", "First paragraph.\n\nSecond paragraph.")])

    assert [paragraph.text for paragraph in result.paragraphs] == [
        "First paragraph.",
        "Second paragraph.",
    ]


def test_english_and_german_soft_hyphenation_is_repaired() -> None:
    result = reconstruct_paragraphs(
        [
            block("b1", "This is a recov-\nered word."),
            block("b2", "Das ist ein Zei-\nlenumbruch.", 145, 175),
        ]
    )

    text = " ".join(paragraph.text for paragraph in result.paragraphs)
    assert "recovered" in text
    assert "Zeilenumbruch" in text
    assert result.hyphenation_repairs == 2


def test_risky_hyphenation_is_left_visible() -> None:
    result = reconstruct_paragraphs([block("b1", "A well-\nKnown case.")])

    assert "well- Known" in result.paragraphs[0].text
    assert result.hyphenation_repairs == 0


def test_adjacent_aligned_blocks_merge_only_when_safe() -> None:
    result = reconstruct_paragraphs(
        [
            block("b1", "This sentence continues", 100, 120),
            block("b2", "with a second aligned block.", 128, 148),
        ]
    )

    assert len(result.paragraphs) == 1
    assert "continues with" in result.paragraphs[0].text
