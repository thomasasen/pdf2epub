# Architecture - Pipeline

The product is a PDF2EPUB converter. Internally it uses a recovery pipeline because PDF does not contain EPUB-ready reading structure.

## Target pipeline

```text
PDF
-> profile
-> extract
-> normalize
-> clean page artifacts
-> resolve reading order
-> reconstruct paragraphs
-> classify tables/images/footnotes
-> build document IR
-> render EPUB
-> validate
-> write quality report
```

## MVP 1 pipeline

The first implemented vertical slice is deliberately narrower:

```text
native-text PDF
-> PyMuPDF profile
-> PyMuPDF text, simple image, and highlight-rectangle extraction
-> safe page artifact removal
-> simple reading order with conservative clear two-column fallback
-> PDF table-of-contents detection and dot-leader cleanup
-> simple table-like block detection before paragraph merging
-> simple paragraph reconstruction
-> DocumentIR
-> stdlib-based EPUB writer with OPF, NAV, NCX, XHTML, CSS, and assets
-> JSON quality report
-> optional debug JSON
```

The current slice prefers warnings and preserved text over aggressive cleanup. It does not run OCR, fully reconstruct complex tables, or solve complex multi-column reading order. Simple extractable PNG, JPEG, and GIF images are preserved; unsupported image cases are reported. Obvious text-table blocks are rendered as semantic XHTML tables when reliable and as readable fallbacks otherwise.

## Main layers

### 1. Profiling

Purpose:
- inspect document before conversion
- identify native text vs image-only/no-text pages
- estimate layout complexity
- decide whether EPUB conversion is sensible

MVP implementation:
- `profiling/profiler.py`
- PyMuPDF when available
- header/regex fallback only if the engine cannot open the file

### 2. Extraction

Purpose:
- extract raw facts from the PDF
- keep geometry and provenance
- avoid normalization that could lose source content

MVP implementation:
- `extraction/pymupdf_extractor.py`
- extracts page size, text blocks, simple image bytes/metadata, detectable filled highlight rectangles, bbox, ids, engine, confidence, and empty-page warnings

### 3. Cleaning

Purpose:
- detect and remove page artifacts
- preserve removed artifacts in the report

MVP implementation:
- `cleaning/page_artifacts.py`
- removes only sequence-like page numbers, simple English/German page labels, and repeated top/bottom margin text
- `--keep-artifacts` bypasses removal

### 4. Reading order

Purpose:
- turn positioned PDF blocks into natural reading order
- support one-column first
- use conservative column-aware ordering when two columns are clearly separated
- report multi-column uncertainty

MVP implementation:
- `reading_order/resolver.py`
- sorts one-column pages by page, y, x
- orders clearly separated two-column pages left column before right column
- emits `possible_multi_column_reading_order_uncertain` when the profile suspects columns

### 5. Structure

Purpose:
- detect and preserve PDF table-of-contents pages as readable structure
- reconstruct paragraphs
- repair safe line wrapping and hyphenation
- preserve paragraph breaks when unsure
- detect obvious table-like text before paragraph merging
- keep highlighted callout/sidebar text separate from regular paragraphs when possible

MVP implementation:
- `structure/toc.py`
- `structure/paragraphs.py`
- `structure/tables.py`
- detects common TOC titles and dot-leader/page-label entry patterns
- removes TOC dot leaders and preserves page labels without creating unsafe links
- merges lines inside blocks
- cautiously merges adjacent aligned blocks
- supports `--no-dehyphenate`
- renders reliable delimited tables semantically and preserves uncertain table-like content with readable fallbacks
- marks paragraphs from highlighted regions as `callout` elements and merges adjacent callout blocks conservatively

### 6. Images

Purpose:
- preserve straightforward embedded images
- keep image provenance and source pages
- report unsupported image cases instead of silently dropping them

MVP implementation:
- PyMuPDF-extracted PNG, JPEG, and GIF image bytes become `image` elements in the IR
- masked/transparent or unsupported image formats are counted and warned in the report

### 7. Rendering

Purpose:
- generate semantic EPUB
- keep XHTML and CSS reader-friendly
- avoid fixed layout
- preserve recovered structure without pretending to be pixel-perfect

MVP implementation:
- `rendering/epub.py`
- `rendering/xhtml.py`
- `rendering/css.py`
- uses a small project-owned EPUB writer built on `zipfile`
- writes `mimetype`, `container.xml`, OPF package metadata, EPUB 3 NAV, NCX fallback, XHTML, CSS, and image assets
- renders paragraphs, bullet lists, PDF TOC entries, callouts, tables, and simple images as semantic XHTML
- turns plain `http://` and `https://` web addresses into external links

### 8. Validation

Purpose:
- run EPUBCheck when available
- fail clearly when validation is not configured

MVP implementation:
- `validation/epubcheck.py`
- `validate` returns a clear message if `epubcheck` is missing from `PATH`

### 9. Debug artifacts

Purpose:
- inspect conversion decisions without changing EPUB output
- show removed page artifacts, reading-order-resolved kept blocks, kept margin blocks, table fallbacks, images, and full IR structure
- keep debug JSON deterministic and avoid dumping binary image bytes

MVP implementation:
- `debug.py`
- `convert --debug-dir` writes `profile.json`, `document-ir.json`, `removed-artifacts.json`, `ordered-blocks.json`, and `kept-margin-blocks.json`
- `table-fallbacks.json` is written when table fallback elements exist
- `images.json` is written when image occurrences exist

## Early design choice

The internal document IR is the core product asset. Every stage should preserve provenance and confidence, and every lossy decision should be visible in the quality report.
