# Architecture - Pipeline

The project is a recovery pipeline, not a direct converter.

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
-> PyMuPDF text block extraction
-> safe page artifact removal
-> simple reading order
-> simple paragraph reconstruction
-> DocumentIR
-> EbookLib EPUB
-> JSON quality report
```

MVP 1 prefers warnings and preserved text over aggressive cleanup. It does not run OCR, reconstruct complex tables, preserve images in EPUB output, or solve multi-column reading order.

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
- extracts page size, text blocks, block bbox, block id, engine, confidence, and empty-page warnings

### 3. Cleaning

Purpose:
- detect and remove page artifacts
- preserve removed artifacts in the report

MVP implementation:
- `cleaning/page_artifacts.py`
- removes only sequence-like numeric page numbers and repeated top/bottom margin text
- `--keep-artifacts` bypasses removal

### 4. Reading order

Purpose:
- turn positioned PDF blocks into natural reading order
- support one-column first
- report multi-column uncertainty

MVP implementation:
- `reading_order/resolver.py`
- sorts by page, y, x
- emits `possible_multi_column_reading_order_uncertain` when the profile suspects columns

### 5. Structure

Purpose:
- reconstruct paragraphs
- repair safe line wrapping and hyphenation
- preserve paragraph breaks when unsure

MVP implementation:
- `structure/paragraphs.py`
- merges lines inside blocks
- cautiously merges adjacent aligned blocks
- supports `--no-dehyphenate`

### 6. Rendering

Purpose:
- generate semantic EPUB
- keep XHTML and CSS reader-friendly
- avoid fixed layout

MVP implementation:
- `rendering/epub.py`
- `rendering/xhtml.py`
- `rendering/css.py`
- uses EbookLib

### 7. Validation

Purpose:
- run EPUBCheck when available
- fail clearly when validation is not configured

MVP implementation:
- `validation/epubcheck.py`
- `validate` returns a clear message if `epubcheck` is missing from `PATH`

## Early design choice

The internal document IR is the core product asset. Every stage should preserve provenance and confidence, and every lossy decision should be visible in the quality report.
