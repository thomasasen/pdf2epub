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
- `DocumentTable`
- `DocumentTocEntry`
- `DocumentElement`
- `RemovedArtifact`
- `DocumentIR`
- `QualityReport`

## Element types

Current implementation renders:
- `paragraph`
- `callout`
- `image`
- `table`
- `toc`
- `warning`

Reserved future element types:
- `heading`
- `caption`
- `footnote`
- `page_artifact`

## Current structure notes

- `paragraph` preserves reconstructed text and source refs. Paragraphs that came from detectable highlighted regions can become `callout` elements.
- `callout` is a heuristic recovery of highlighted/sidebar-like source blocks. It is not a promise that the original visual design was fully understood.
- `image` preserves simple embedded PNG, JPEG, and GIF image bytes with provenance when PyMuPDF can extract them directly.
- `table` can carry a structured `DocumentTable` for reliable row/cell reconstruction. If that is not reliable, the element keeps source text and renders as a readable fallback.
- `toc` carries `DocumentTocEntry` entries recovered from PDF table-of-contents pages. Dot leaders are removed and page labels are kept, but internal EPUB links are not resolved yet.
- `warning` is available for explicit warning elements, although most current warnings live in the quality report.

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
          "message": "Possible block-structured table was preserved as a preformatted fallback because reliable cell reconstruction is not implemented yet.",
          "severity": "warning",
          "page_index": 1
        }
      ]
    },
    {
      "element_id": "toc-p0002",
      "element_type": "toc",
      "text": "Inhaltsverzeichnis",
      "source_refs": [],
      "confidence": 0.72,
      "warnings": [
        {
          "code": "toc_links_not_resolved",
          "message": "Table of contents was detected and cleaned, but EPUB links were not created because destination anchors are not resolved yet.",
          "severity": "info",
          "page_index": 1
        }
      ],
      "toc_entries": [
        {
          "title": "1. Was MEDDICC ist - und was nicht",
          "level": 1,
          "page_label": "6"
        }
      ]
    }
  ],
  "removed_artifacts": [],
  "warnings": []
}
```
