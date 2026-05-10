from __future__ import annotations

from pdf2epub_recovery.cleaning.page_artifacts import remove_page_artifacts
from pdf2epub_recovery.model import BBox, RawTextBlock


def block(block_id: str, page: int, text: str, y0: float, y1: float) -> RawTextBlock:
    return RawTextBlock(
        block_id=block_id,
        page_index=page,
        page_width=300,
        page_height=400,
        raw_text=text,
        bbox=BBox(40, y0, 260, y1),
        source_engine="test",
    )


def test_page_numbers_are_removed_when_sequence_like() -> None:
    blocks = [
        block("b1", 0, "Body one", 120, 140),
        block("n1", 0, "1", 380, 392),
        block("b2", 1, "Body two", 120, 140),
        block("n2", 1, "2", 380, 392),
        block("b3", 2, "Body three", 120, 140),
        block("n3", 2, "3", 380, 392),
    ]

    result = remove_page_artifacts(blocks)

    assert [artifact.text for artifact in result.removed_artifacts] == ["1", "2", "3"]
    assert all(artifact.artifact_type == "page_number" for artifact in result.removed_artifacts)
    assert [kept.raw_text for kept in result.kept_blocks] == ["Body one", "Body two", "Body three"]


def test_german_page_labels_are_removed_when_sequence_like() -> None:
    blocks = [
        block("b1", 0, "Body one", 120, 140),
        block("n1", 0, "Seite 1", 380, 392),
        block("b2", 1, "Body two", 120, 140),
        block("n2", 1, "Seite 2", 380, 392),
        block("b3", 2, "Body three", 120, 140),
        block("n3", 2, "Seite 3", 380, 392),
    ]

    result = remove_page_artifacts(blocks)

    assert [artifact.text for artifact in result.removed_artifacts] == [
        "Seite 1",
        "Seite 2",
        "Seite 3",
    ]
    assert [kept.raw_text for kept in result.kept_blocks] == ["Body one", "Body two", "Body three"]


def test_page_labels_are_only_removed_in_margins() -> None:
    blocks = [
        block("b1", 0, "See Seite 1 for details.", 120, 140),
        block("b2", 1, "See Seite 2 for details.", 120, 140),
    ]

    result = remove_page_artifacts(blocks)

    assert not result.removed_artifacts
    assert [kept.raw_text for kept in result.kept_blocks] == [
        "See Seite 1 for details.",
        "See Seite 2 for details.",
    ]


def test_repeated_header_is_removed() -> None:
    blocks = [
        block("h1", 0, "Book Header", 22, 34),
        block("b1", 0, "Body one", 120, 140),
        block("h2", 1, "Book Header", 22, 34),
        block("b2", 1, "Body two", 120, 140),
    ]

    result = remove_page_artifacts(blocks)

    assert [artifact.artifact_type for artifact in result.removed_artifacts] == ["header", "header"]
    assert [kept.raw_text for kept in result.kept_blocks] == ["Body one", "Body two"]


def test_unique_margin_text_is_not_removed() -> None:
    blocks = [
        block("u1", 0, "Chapter One", 22, 34),
        block("b1", 0, "Body one", 120, 140),
        block("u2", 1, "A different opening line", 22, 34),
        block("b2", 1, "Body two", 120, 140),
    ]

    result = remove_page_artifacts(blocks)

    assert not result.removed_artifacts
    assert len(result.kept_blocks) == 4
