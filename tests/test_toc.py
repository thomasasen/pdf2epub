from __future__ import annotations

from pdf2epub_recovery.model import BBox, RawTextBlock
from pdf2epub_recovery.structure.toc import detect_toc_blocks


def block(block_id: str, text: str, page_index: int = 0) -> RawTextBlock:
    return RawTextBlock(
        block_id=block_id,
        page_index=page_index,
        page_width=600,
        page_height=800,
        raw_text=text,
        bbox=BBox(40, 80, 540, 100),
        source_engine="test",
    )


def test_detects_toc_page_and_cleans_dot_leader_entries() -> None:
    result = detect_toc_blocks(
        [
            block("p0001-b0001", "Inhaltsverzeichnis"),
            block("p0001-b0002", "2\nSo liest du dieses Dokument"),
            block("p0001-b0003", "6\n1. Was MEDDICC ist - und was nicht"),
            block(
                "p0001-b0004",
                ". . . . . . . . . . . . . . . . . . . . . 6\n"
                "Was MEDDICC nicht ist",
            ),
            block(
                "p0001-b0005",
                ". . . . . . . . . . . . . . . . . . . . . 6\n"
                "Wann MEDDICC besonders nützlich ist",
            ),
            block("p0002-b0001", "Normal body text.", page_index=1),
        ]
    )

    assert [block.block_id for block in result.text_blocks] == ["p0002-b0001"]
    assert len(result.toc_blocks) == 5
    assert len(result.toc_elements) == 1
    entries = result.toc_elements[0].toc_entries
    assert [(entry.title, entry.page_label) for entry in entries] == [
        ("So liest du dieses Dokument", "2"),
        ("1. Was MEDDICC ist - und was nicht", "6"),
        ("Was MEDDICC nicht ist", "6"),
        ("Wann MEDDICC besonders nützlich ist", "6"),
    ]
    assert result.warnings[0].code == "toc_links_not_resolved"


def test_does_not_detect_ordinary_numbered_text_as_toc() -> None:
    result = detect_toc_blocks(
        [
            block("p0001-b0001", "1. First body heading"),
            block("p0001-b0002", "This paragraph mentions 2026 and 42."),
            block("p0001-b0003", "Another ordinary paragraph."),
        ]
    )

    assert len(result.text_blocks) == 3
    assert result.toc_blocks == []
    assert result.toc_elements == []


def test_detects_toc_continuation_page_without_repeated_title() -> None:
    result = detect_toc_blocks(
        [
            block("p0001-b0001", "Inhaltsverzeichnis"),
            block("p0001-b0002", "2\nOverview"),
            block("p0001-b0003", "3\n1. Start"),
            block("p0001-b0004", ". . . . . . . . . . 3\nDetails"),
            block("p0002-b0001", ". . . . . . . . . . 9\nLater details", page_index=1),
            block("p0002-b0002", "10\n2. Later chapter", page_index=1),
            block("p0002-b0003", "11\n3. Last chapter", page_index=1),
            block("p0003-b0001", "1. Body starts here", page_index=2),
        ]
    )

    assert {block.page_index for block in result.toc_blocks} == {0, 1}
    assert len(result.toc_elements) == 1
    assert result.toc_elements[0].toc_entries[-1].title == "3. Last chapter"
    assert [block.block_id for block in result.text_blocks] == ["p0003-b0001"]


def test_splits_multiple_toc_entries_inside_one_pdf_block() -> None:
    result = detect_toc_blocks(
        [
            block("p0001-b0001", "Inhaltsverzeichnis"),
            block(
                "p0001-b0002",
                "1\nEinführung........................................................................18\n"
                "2\nStrategieverständnis ......................................................21\n"
                "2.1\nHistorie............................................................................22",
            ),
            block("p0002-b0001", "1 Einführung", page_index=1),
        ]
    )

    assert [entry.title for entry in result.toc_elements[0].toc_entries] == [
        "1 Einführung",
        "2 Strategieverständnis",
        "2.1 Historie",
    ]
    assert [entry.page_label for entry in result.toc_elements[0].toc_entries] == [
        "18",
        "21",
        "22",
    ]
