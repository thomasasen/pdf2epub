# Roadmap

This project follows short vertical slices.

## Phase 0 - Bootstrap

- [x] Repository skeleton.
- [x] Python package structure.
- [x] CLI entry point.
- [x] Basic docs.
- [x] Basic tests.
- [ ] Initial GitHub repository.
- [ ] CI pipeline.

## MVP 1 - Native-text one-column EPUB slice

- [x] Real profile command with PyMuPDF.
- [x] Page count, page sizes, native text counts, no-text page estimates.
- [x] Layout estimate: `one_column`, `possible_multi_column`, `unknown`.
- [x] Raw text block extraction with bbox and source provenance.
- [x] Conservative page number/header/footer removal.
- [x] Trace removed artifacts in the quality report.
- [x] Simple one-column reading order.
- [x] Multi-column uncertainty warning.
- [x] Simple paragraph reconstruction.
- [x] Conservative dehyphenation and `--no-dehyphenate`.
- [x] Basic EPUB generation.
- [x] Optional JSON quality report via `--report`.
- [x] Clear optional EPUBCheck validation behavior.
- [x] Simple local web interface with progress and log.
- [x] Web upload supports drag-and-drop.
- [x] Web options include plain-language explanations.
- [x] EPUB output has reader-friendly CSS and basic paragraph spacing.
- [x] Blank lines inside extracted blocks preserve paragraph breaks.

MVP 1 intentionally does not implement OCR, complex table reconstruction, hosted/multi-user workflows, or multi-engine extraction.

## Next slice - Preserve simple non-text content

- [x] Preserve simple embedded images in EPUB output.
- [x] Warn with image counts and source pages when images cannot be preserved.
- [x] Detect obvious table-like blocks.
- [x] Render simple text tables or use a safe fallback.
- [x] Add debug artifacts for removed content and ordered blocks.

## Future - Better layout recovery

- [ ] Stronger multi-column detection.
- [ ] Column-aware reading order.
- [ ] Heading detection.
- [ ] Footnote detection.
- [ ] Paragraph reconstruction confidence per page.
- [ ] Human-readable profile/report output.

## Future - Validation and distribution

- [ ] Optional EPUBCheck setup documentation.
- [ ] CI pipeline.
- [ ] Packaged CLI release.

## Later - OCR and multi-engine

- [ ] OCR adapter.
- [ ] Marker adapter.
- [ ] Docling adapter.
- [ ] Engine comparison.
- [ ] Auto mode with explainable selection.
