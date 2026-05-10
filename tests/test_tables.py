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
    assert result.table_elements[0].table is not None
    assert result.table_elements[0].table.rows == [
        ["Name", "Score", "Grade"],
        ["Ada", "98", "A"],
        ["Grace", "91", "A"],
    ]
    assert result.warnings == []


def test_uncertain_table_like_text_uses_preformatted_fallback() -> None:
    result = detect_table_like_blocks(
        [
            block(
                "Name Score Grade\n"
                "Ada         98          A\n"
                "Grace       91          A"
            )
        ]
    )

    assert len(result.table_blocks) == 1
    assert result.text_blocks == []
    assert result.table_elements[0].element_type == "table"
    assert result.table_elements[0].table is None
    assert result.warnings[0].code == "table_fallback_used"


def test_plain_wrapped_text_is_not_table_like() -> None:
    result = detect_table_like_blocks(
        [block("This is a normal paragraph\nthat merely wraps onto another line.")]
    )

    assert result.table_blocks == []
    assert len(result.text_blocks) == 1
    assert result.table_elements == []


def test_detects_block_structured_table_as_preformatted_fallback() -> None:
    blocks = [
        RawTextBlock(
            block_id="p0001-b0001",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Feld\nInhalt",
            bbox=BBox(40, 100, 260, 115),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Anbieter\nNovaFlow - Enterprise CRM",
            bbox=BBox(40, 130, 260, 145),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Kunde\nAuron Maschinenbau Gruppe",
            bbox=BBox(40, 160, 260, 175),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0004",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Sales-Zyklus\nca. 5 bis 7 Monate",
            bbox=BBox(40, 190, 260, 205),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert len(result.table_blocks) == 4
    assert result.text_blocks == []
    assert result.table_elements[0].element_type == "table"
    assert result.table_elements[0].table is None
    assert "Feld | Inhalt" in result.table_elements[0].text
    assert "Sales-Zyklus | ca. 5 bis 7 Monate" in result.table_elements[0].text
    assert result.warnings[0].code == "table_fallback_used"


def test_splits_multiline_left_block_against_header_column_count() -> None:
    blocks = [
        RawTextBlock(
            block_id="p0001-b0001",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Variante\nZusatz\nPraktische Bedeutung",
            bbox=BBox(70, 100, 370, 110),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="MEDDIC\n6 Kernelemente",
            bbox=BBox(70, 130, 230, 140),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Grundgerüst für Qualifizierung",
            bbox=BBox(250, 125, 520, 150),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0004",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="MEDDICC\nzusätzlich\nCompetition",
            bbox=BBox(70, 165, 230, 190),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0005",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="macht alternative Optionen sichtbar",
            bbox=BBox(250, 165, 520, 190),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert result.text_blocks == []
    assert "Variante | Zusatz | Praktische Bedeutung" in result.table_elements[0].text
    assert "MEDDIC | 6 Kernelemente | Grundgerüst für Qualifizierung" in (
        result.table_elements[0].text
    )
    assert "MEDDICC | zusätzlich Competition | macht alternative Optionen sichtbar" in (
        result.table_elements[0].text
    )


def test_splits_three_column_phase_table_with_wrapped_header_and_first_cell() -> None:
    blocks = [
        RawTextBlock(
            block_id="p0001-b0001",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Element\nZwischenstan\nd\nWas noch fehlt",
            bbox=BBox(70, 100, 330, 120),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Pain\nhoch\nFolgen für CFO und Geschäftsführung sauber\nquantifizieren.",
            bbox=BBox(70, 135, 500, 160),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Economic\nBuyer\noffen\ndirekter Zugang zum CRO oder CFO fehlt noch.",
            bbox=BBox(70, 175, 500, 205),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert result.text_blocks == []
    assert "Element | Zwischenstand | Was noch fehlt" in result.table_elements[0].text
    assert "Pain | hoch | Folgen für CFO und Geschäftsführung sauber quantifizieren." in (
        result.table_elements[0].text
    )
    assert "Economic Buyer | offen | direkter Zugang zum CRO oder CFO fehlt noch." in (
        result.table_elements[0].text
    )


def test_merges_known_meddicc_terms_split_across_pdf_lines() -> None:
    blocks = [
        RawTextBlock(
            block_id="p0001-b0001",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Feld\n0 Punkte\n1 Punkt\n2 Punkte",
            bbox=BBox(70, 100, 500, 120),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Economic\nBuyer\nkein Zugriff\nindirekter Zugriff\ndirekter Austausch",
            bbox=BBox(70, 135, 500, 160),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=560,
            page_height=800,
            raw_text="Decision\nCriteria\nunscharf\nteilweise bekannt\npriorisiert",
            bbox=BBox(70, 175, 500, 205),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert "Economic Buyer | kein Zugriff | indirekter Zugriff | direkter Austausch" in (
        result.table_elements[0].text
    )
    assert "Decision Criteria | unscharf | teilweise bekannt | priorisiert" in (
        result.table_elements[0].text
    )


def test_detects_split_cell_table_as_preformatted_fallback() -> None:
    blocks = [
        block("Element"),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Leitfrage",
            bbox=BBox(120, 100, 180, 110),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Status",
            bbox=BBox(200, 100, 250, 110),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0004",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Metrics",
            bbox=BBox(40, 125, 90, 135),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0005",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Ist der Effekt quantifiziert?",
            bbox=BBox(120, 125, 190, 145),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0006",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="rot/gelb/grün",
            bbox=BBox(200, 125, 270, 135),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0007",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Competitio\nn",
            bbox=BBox(40, 155, 100, 165),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0008",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Handelt jemand intern?",
            bbox=BBox(120, 155, 190, 175),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0009",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="rot/gelb/grün",
            bbox=BBox(200, 155, 270, 165),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert len(result.table_blocks) == 9
    assert result.text_blocks == []
    assert "Element | Leitfrage | Status" in result.table_elements[0].text
    assert "Competition | Handelt jemand intern? | rot/gelb/grün" in result.table_elements[0].text


def test_consecutive_wrapped_paragraphs_are_not_geometry_table() -> None:
    blocks = [
        block("This is a normal paragraph\nthat wraps onto a second line."),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="Another paragraph also wraps\nbecause the text box is narrow.",
            bbox=BBox(40, 180, 260, 220),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="A third paragraph still should\nremain normal prose.",
            bbox=BBox(40, 240, 260, 280),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert result.table_blocks == []
    assert len(result.text_blocks) == 3


def test_bullet_like_blocks_are_not_geometry_tables() -> None:
    blocks = [
        RawTextBlock(
            block_id="p0001-b0001",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="n First bullet wraps\nonto a second line.",
            bbox=BBox(40, 100, 260, 125),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0002",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="n Second bullet wraps\nonto a second line.",
            bbox=BBox(40, 132, 260, 157),
            source_engine="test",
        ),
        RawTextBlock(
            block_id="p0001-b0003",
            page_index=0,
            page_width=300,
            page_height=400,
            raw_text="n Third bullet wraps\nonto a second line.",
            bbox=BBox(40, 164, 260, 189),
            source_engine="test",
        ),
    ]

    result = detect_table_like_blocks(blocks)

    assert result.table_blocks == []
    assert len(result.text_blocks) == 3
