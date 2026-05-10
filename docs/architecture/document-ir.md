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
- `ExtractedPage`
- `ExtractedDocument`
- `PageProfile`
- `PdfProfile`
- `Paragraph`
- `DocumentElement`
- `RemovedArtifact`
- `DocumentIR`
- `QualityReport`

## Element types

MVP 1 renders:
- `paragraph`

Reserved future element types:
- `heading`
- `table`
- `image`
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
    }
  ],
  "removed_artifacts": [],
  "warnings": []
}
```
