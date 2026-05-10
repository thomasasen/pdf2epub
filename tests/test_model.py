from __future__ import annotations

from pdf2epub_recovery.model import BBox, DocumentElement, DocumentIR, QualityReport, ReportActions


def test_ir_and_report_are_json_compatible() -> None:
    ir = DocumentIR(
        metadata={"title": "Example"},
        elements=[
            DocumentElement(
                element_id="p0001",
                element_type="paragraph",
                text="Text",
                source_refs=[],
            )
        ],
    )
    report = QualityReport(
        input_path="in.pdf",
        output_path="out.epub",
        status="ok",
        quality_score=90,
        page_count=1,
        native_text_page_count=1,
        image_only_or_no_text_page_count=0,
        total_raw_blocks=1,
        total_paragraphs=1,
        actions=ReportActions(),
    )

    assert ir.to_dict()["elements"][0]["text"] == "Text"
    assert report.to_dict()["actions"]["page_numbers_removed"] == 0
    assert BBox(1, 2, 3, 4).to_list() == [1, 2, 3, 4]
