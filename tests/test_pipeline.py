from __future__ import annotations

from pdf2epub_recovery.model import (
    BBox,
    ExtractedDocument,
    ExtractedImage,
    ExtractedPage,
    RawTextBlock,
)
from pdf2epub_recovery.pipeline import _decorative_image_ids, _image_elements_and_warnings


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


def test_repeated_small_margin_images_are_removed_as_decorative() -> None:
    pages = [
        ExtractedPage(
            page_index=index,
            width=300,
            height=420,
            images=[
                ExtractedImage(
                    image_id=f"p{index + 1:04d}-img0001",
                    page_index=index,
                    page_width=300,
                    page_height=420,
                    bbox=BBox(10, 390, 24, 404),
                    source_engine="test",
                    xref=10,
                    extension="png",
                    media_type="image/png",
                    data=b"logo",
                    pixel_width=32,
                    pixel_height=32,
                )
            ],
            image_count=1,
        )
        for index in range(3)
    ]
    extracted = ExtractedDocument(input_path="sample.pdf", source_engine="test", pages=pages)

    decorative_ids = _decorative_image_ids(extracted)
    elements, warnings = _image_elements_and_warnings(
        extracted,
        decorative_image_ids=decorative_ids,
    )

    assert decorative_ids == {"p0001-img0001", "p0002-img0001", "p0003-img0001"}
    assert elements == []
    assert warnings == []


def test_nearby_caption_becomes_image_alt_text() -> None:
    extracted = ExtractedDocument(
        input_path="sample.pdf",
        source_engine="test",
        pages=[
            ExtractedPage(
                page_index=0,
                width=300,
                height=420,
                text_blocks=[
                    RawTextBlock(
                        block_id="p0001-b0001",
                        page_index=0,
                        page_width=300,
                        page_height=420,
                        raw_text="Abb. 1: Example image",
                        bbox=BBox(80, 250, 220, 265),
                        source_engine="test",
                    )
                ],
                images=[
                    ExtractedImage(
                        image_id="p0001-img0001",
                        page_index=0,
                        page_width=300,
                        page_height=420,
                        bbox=BBox(70, 130, 230, 230),
                        source_engine="test",
                        extension="png",
                        media_type="image/png",
                        data=b"image",
                    )
                ],
                image_count=1,
            )
        ],
    )

    elements, warnings = _image_elements_and_warnings(extracted)

    assert warnings == []
    assert elements[0].image is not None
    assert elements[0].image.alt_text == "Abb. 1: Example image"
