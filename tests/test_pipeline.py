from __future__ import annotations

from pdf2epub_recovery.model import BBox, ExtractedDocument, ExtractedImage, ExtractedPage
from pdf2epub_recovery.pipeline import _image_elements_and_warnings


def test_unsupported_image_is_reported() -> None:
    extracted = ExtractedDocument(
        input_path="sample.pdf",
        source_engine="test",
        pages=[
            ExtractedPage(
                page_index=0,
                width=300,
                height=420,
                images=[
                    ExtractedImage(
                        image_id="p0001-img0001",
                        page_index=0,
                        page_width=300,
                        page_height=420,
                        bbox=BBox(10, 20, 100, 120),
                        source_engine="test",
                        extension="tiff",
                        media_type=None,
                        data=None,
                    )
                ],
                image_count=1,
            )
        ],
    )

    elements, warnings = _image_elements_and_warnings(extracted)

    assert elements == []
    assert warnings[0].code == "image_not_preserved"
    assert "page 1" in warnings[0].message
