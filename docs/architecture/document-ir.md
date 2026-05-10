# Architecture - Document IR

The document IR is the internal representation between extraction and rendering.

## Requirements

Every meaningful element should carry:
- stable id
- element type
- source pages
- source bounding boxes when available
- raw or normalized text when available
- confidence
- warnings
- source engine
- provenance

## MVP 1 models

The current implementation keeps the model intentionally small:
- `BBox`
- `SourceRef`
- `RawTextBlock`
- `ExtractedImage`
- `ExtractedPage`
- `ExtractedDocument`
- `PageProfile`
- `PdfProfile`
- `Paragraph`
- `DocumentImage`
- `DocumentElement`
- `RemovedArtifact`
- `DocumentIR`
- `QualityReport`

## Element types

Current MVP renders:
- `paragraph`
- `image`
- `table`

Reserved future element types:
- `heading`
- `caption`
- `footnote`
- `page_artifact`
- `warning`

## Design rule

Do not lose source provenance.

If a paragraph was created from multiple PDF blocks, the IR must know that. If a page number was removed, the report must know which text was removed, where it came from, and why.

## Example JSON shape

```json
{
  "metadata": {
    "title": "Unknown",
    "author": null,
    "language": "en"
  },
  "elements": [
    {
      "element_id": "p0001",
      "element_type": "paragraph",
      "text": "Recovered paragraph text.",
      "source_refs": [
        {
          "page_index": 0,
          "block_id": "p0001-b0001",
          "bbox": {
            "x0": 72.0,
            "y0": 120.0,
            "x1": 520.0,
            "y1": 155.0
          },
          "engine": "pymupdf"
        }
      ],
      "confidence": 0.9,
      "warnings": []
    },
    {
      "element_id": "p0001-img0001",
      "element_type": "image",
      "text": "Image from page 1",
      "source_refs": [
        {
          "page_index": 0,
          "block_id": "p0001-img0001",
          "bbox": {
            "x0": 90.0,
            "y0": 145.0,
            "x1": 210.0,
            "y1": 245.0
          },
          "engine": "pymupdf"
        }
      ],
      "confidence": 0.85,
      "warnings": [],
      "image": {
        "image_id": "p0001-img0001",
        "file_name": "images/p0001-img0001.png",
        "media_type": "image/png",
        "data": {
          "byte_count": 91,
          "sha256": "..."
        },
        "alt_text": "Image from page 1",
        "source_refs": [
          {
            "page_index": 0,
            "block_id": "p0001-img0001",
            "bbox": {
              "x0": 90.0,
              "y0": 145.0,
              "x1": 210.0,
              "y1": 245.0
            },
            "engine": "pymupdf"
          }
        ]
      }
    },
    {
      "element_id": "table-p0002-b0004",
      "element_type": "table",
      "text": "Name        Score\nAda         98",
      "source_refs": [
        {
          "page_index": 1,
          "block_id": "p0002-b0004",
          "bbox": {
            "x0": 55.0,
            "y0": 135.0,
            "x1": 260.0,
            "y1": 170.0
          },
          "engine": "pymupdf"
        }
      ],
      "confidence": 0.65,
      "warnings": [
        {
          "code": "table_fallback_used",
          "message": "Possible table-like text was preserved as a preformatted fallback; full table reconstruction is not implemented.",
          "severity": "warning",
          "page_index": 1
        }
      ]
    }
  ],
  "removed_artifacts": [],
  "warnings": []
}
```
