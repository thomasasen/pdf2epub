# Quality Report

The quality report is a first-class feature.

A user should know whether the EPUB is trustworthy before reading 300 pages. MVP 1 writes the report as JSON when `convert --report` is passed.

## Report goals

The report answers:
- What kind of PDF is this?
- How much native text was extracted?
- Were pages image-only or textless?
- Were page numbers, headers, or footers removed?
- Was reading order uncertain?
- Were unsupported features detected?
- Was EPUB validation run?
- Which warnings need manual review?

## MVP 1 JSON shape

```json
{
  "input_path": "book.pdf",
  "output_path": "book.epub",
  "status": "warning",
  "quality_score": 85,
  "page_count": 214,
  "native_text_page_count": 212,
  "image_only_or_no_text_page_count": 2,
  "total_raw_blocks": 980,
  "total_paragraphs": 611,
  "actions": {
    "page_numbers_removed": 198,
    "headers_removed": 41,
    "footers_removed": 41,
    "hyphenations_repaired": 312,
    "line_wraps_repaired": 927
  },
  "removed_artifacts": [
    {
      "artifact_id": "a-page-number-p0001-b0003",
      "artifact_type": "page_number",
      "text": "1",
      "source_ref": {
        "page_index": 0,
        "block_id": "p0001-b0003",
        "bbox": {
          "x0": 146.0,
          "y0": 392.0,
          "x1": 152.0,
          "y1": 402.0
        },
        "engine": "pymupdf"
      },
      "reason": "Numeric margin text follows a repeated page-number sequence.",
      "confidence": 0.95
    }
  ],
  "reading_order_warnings": [],
  "unsupported_feature_warnings": [],
  "warnings": [],
  "dependency_notes": [
    "PyMuPDF used for native text extraction.",
    "EbookLib used for basic EPUB writing.",
    "EPUBCheck is optional and not run during conversion."
  ],
  "validation": {
    "epubcheck": "not_run"
  }
}
```

## Status

- `ok`: conversion completed without warnings.
- `warning`: conversion completed, but uncertainty or unsupported content was reported.
- `error`: conversion failed or the input was not a readable PDF.

## Scoring model

MVP 1 uses a simple explainable score starting at 100 and subtracting for:
- textless/image-only pages
- possible multi-column layout
- reading-order warnings
- unsupported detected features, such as images not yet rendered
- zero extracted text

The score is not a promise of perfect conversion. It is a compact risk signal backed by the detailed warnings and action counts.
