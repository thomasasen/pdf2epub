# Quality Report

The quality report is a first-class feature.

A user should know whether the EPUB is trustworthy before reading 300 pages. The converter writes the report as JSON when `convert --report` is passed.

For developer inspection, `convert --debug-dir` also writes separate debug JSON files for removed artifacts, ordered blocks, kept margin blocks, table fallbacks, detected images, and the full document IR.

## Report goals

The report answers:
- What kind of PDF is this?
- How much native text was extracted?
- Were pages image-only or textless?
- Were page numbers, headers, or footers removed?
- Was reading order uncertain?
- Were unsupported features detected?
- Were detected images preserved or reported as unsupported?
- Were table-like blocks rendered semantically or preserved with a fallback?
- Was a PDF table of contents detected and preserved without unsafe links?
- Were simple callouts, bullet lists, and clickable web links recovered in EPUB output?
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
    "line_wraps_repaired": 927,
    "images_detected": 6,
    "images_preserved": 4,
    "images_not_preserved": 2,
    "table_like_blocks_detected": 3,
    "tables_rendered_semantically": 1,
    "table_fallbacks_rendered": 2
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
  "unsupported_feature_warnings": [
    {
      "code": "image_not_preserved",
      "message": "Image on page 12 was not preserved. Image uses a mask or transparency that is not preserved in this MVP slice.",
      "severity": "warning",
      "page_index": 11
    }
  ],
  "warnings": [
    {
      "code": "table_fallback_used",
      "message": "Possible block-structured table was preserved as a preformatted fallback because reliable cell reconstruction is not implemented yet.",
      "severity": "warning",
      "page_index": 23
    },
    {
      "code": "toc_links_not_resolved",
      "message": "Table of contents was detected and cleaned, but EPUB links were not created because destination anchors are not resolved yet.",
      "severity": "info",
      "page_index": 1
    }
  ],
  "dependency_notes": [
    "PyMuPDF used for native text extraction.",
    "EPUB written with the project stdlib-based minimal EPUB writer.",
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

The current scoring model starts at 100 and subtracts for:
- textless/image-only pages
- possible multi-column layout
- reading-order warnings
- unsupported detected features, such as images that could not be preserved
- zero extracted text

The score is not a promise of perfect conversion. It is a compact risk signal backed by the detailed warnings and action counts.

Some recovered structures, such as PDF table-of-contents entries, callouts, lists, and clickable web links, are currently represented in `document-ir.json` and EPUB output. They do not yet have dedicated action counters in the report.

## Debug JSON

`convert --debug-dir debug` writes:
- `removed-artifacts.json`: removed page numbers, headers, and footers with page, bbox, text, reason, confidence, and source engine.
- `ordered-blocks.json`: text blocks after page artifact cleanup and reading-order resolution.
- `kept-margin-blocks.json`: margin-area blocks that were kept for manual inspection.
- `table-fallbacks.json`: table fallback elements when detected, including source refs, text, confidence, and warnings.
- `images.json`: detected image occurrences when present, including placement, provenance, and preservation status.
- `document-ir.json`: the normalized structure rendered to EPUB, including `paragraph`, `callout`, `toc`, `table`, and `image` elements.

These files are diagnostic artifacts, not a replacement for the user-facing quality report.
