# PDF2EPUB Converter

A local-first PDF-to-EPUB converter.

The goal is not to build a naive file-format wrapper. The converter recovers enough document structure to produce readable EPUB files and reports uncertainty honestly.

## Quick start

From the repository folder:

```powershell
python -m pip install -e ".[dev]"
python -m pdf2epub_recovery web
```

Then open:

```text
http://127.0.0.1:8765/
```

Stop the server with `Ctrl+C` in the terminal where it is running.

If port `8765` is already in use, choose another port:

```powershell
python -m pdf2epub_recovery web --port 8770
```

The installed console script can also be used when it is on your `PATH`:

```powershell
pdf2epub-recovery web
```

On Windows, if `pdf2epub-recovery` is not recognized, use the reliable module form:

```powershell
python -m pdf2epub_recovery web
```

## Current status

This repository has its first converter MVP plus the first document-structure polish needed for real-world PDFs.

Implemented scope:
- Real PDF profiling with PyMuPDF.
- Native text block extraction with geometry and provenance.
- Filled-rectangle highlight detection for simple callout/sidebar conversion.
- Conservative removal of repeated page numbers, headers, and footers.
- Page number cleanup supports simple English and German page labels in margins.
- Simple one-column reading order.
- Basic paragraph reconstruction and conservative dehyphenation.
- Reflowable EPUB output with a small stdlib-based writer, OPF, NAV, and NCX fallback.
- Reader-friendly EPUB CSS, paragraph spacing, table styling, and simple callout styling.
- Bullet-like source paragraphs rendered as XHTML lists.
- Plain `http://` and `https://` web addresses rendered as clickable links.
- Simple embedded image preservation in EPUB output.
- Image preservation counts and unsupported-image warnings in reports.
- Obvious text-table detection with semantic XHTML tables when reliable and visible or preformatted fallbacks otherwise.
- PDF table-of-contents detection that removes dot leaders and keeps page labels as readable text.
- Conservative column-aware reading order for clearly separated two-column pages.
- JSON quality reports.
- CLI-first, local/offline workflow.
- Simple local web interface with progress and conversion log.
- Drag-and-drop PDF upload in the web interface.
- Plain-language explanations for web conversion options.

Supported input:
- Native-text, mostly one-column PDFs.
- Text-centric PDFs with simple repeated page artifacts.
- Simple embedded PNG, JPEG, and GIF images that PyMuPDF can extract directly.
- Obvious text tables with spacing, tabs, or pipe-separated columns.
- Simple PDF table-of-contents pages with dot leaders and page labels.
- Simple highlighted callout/sidebar blocks drawn as filled rectangles.

Known limitations:
- OCR is not implemented.
- Image-only/scanned pages are reported, not recovered.
- Complex tables are not fully reconstructed; unreliable tables use a readable fallback and warnings.
- PDF table-of-contents entries are preserved as readable entries, but internal EPUB links are not resolved yet.
- Highlight/callout conversion is heuristic and depends on detectable PDF drawing rectangles.
- Masked, transparent, transformed, or unusual image encodings may be reported but not preserved.
- Clear two-column pages use a conservative column-aware fallback, but complex multi-column documents may still warn and can have imperfect reading order.
- EPUBCheck validation is optional and only runs if an `epubcheck` executable is configured on `PATH`.
- PyMuPDF is currently a required extraction dependency; it is AGPL/commercial licensed and should be replaced or isolated behind an optional adapter before broader distribution.

## Why this project exists

Most PDF-to-EPUB workflows fail because PDF is page-position based while EPUB is structured, reflowable web content. A good converter must therefore recover document structure before rendering EPUB.

Target pipeline:

```text
PDF
-> profile
-> extract blocks with geometry
-> remove safe page artifacts
-> resolve reading order, including conservative clear two-column fallback
-> detect and clean PDF table-of-contents pages
-> detect obvious text tables before paragraph merging
-> rebuild paragraphs
-> preserve simple callouts, bullet lists, and clickable web links
-> preserve simple images or report unsupported cases
-> render EPUB with a minimal stdlib writer and semantic XHTML
-> report quality
```

Future phases will add stronger table/image handling, better multi-column conversion, optional validation integration, and later OCR/multi-engine workflows.

## Installation for development

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## CLI

The console script is:

```bash
pdf2epub-recovery --help
pdf2epub-recovery profile input.pdf --out profile.json
pdf2epub-recovery extract input.pdf --out debug-extraction.json
pdf2epub-recovery convert input.pdf --out book.epub --report book.report.json
pdf2epub-recovery validate book.epub
pdf2epub-recovery web
```

If `pdf2epub-recovery` is not found on Windows, use the module form from the repository:

```bash
python -m pdf2epub_recovery --help
python -m pdf2epub_recovery web
```

If that also fails, install the package in editable mode first:

```bash
python -m pip install -e ".[dev]"
```

Useful conversion options:

```bash
pdf2epub-recovery convert input.pdf --out book.epub --debug-dir debug
pdf2epub-recovery convert input.pdf --out book.epub --keep-artifacts
pdf2epub-recovery convert input.pdf --out book.epub --no-dehyphenate
pdf2epub-recovery convert input.pdf --out book.epub --max-pages 25
```

`--debug-dir` writes inspection JSON for conversion decisions:
- `profile.json`
- `document-ir.json`
- `removed-artifacts.json`
- `ordered-blocks.json`
- `kept-margin-blocks.json`
- `table-fallbacks.json` when table fallback elements exist
- `images.json` when image occurrences exist

`document-ir.json` is the best place to inspect recovered structure such as `toc`, `callout`, `table`, `image`, and `paragraph` elements.

## Local web interface

Start the browser UI with:

```powershell
python -m pdf2epub_recovery web
```

By default it binds to `127.0.0.1:8765` and opens the browser. The page provides:
- PDF upload.
- Conversion options for artifact keeping, dehyphenation, and page limits.
- Stage-based progress bar.
- Live conversion log.
- Quality summary with table/image/TOC/callout/list/link indicators.
- Concrete warning list from the quality report.
- EPUB, report, and debug JSON download links when conversion finishes.

To choose another port or avoid opening a browser automatically:

```powershell
python -m pdf2epub_recovery web --port 8770 --no-browser
```

## Development commands

```bash
python -m pytest
python -m ruff check .
python -m ruff format .
```

## Repository layout

```text
.
|-- AGENTS.md
|-- README.md
|-- pyproject.toml
|-- docs/
|-- src/
|   `-- pdf2epub_recovery/
`-- tests/
```

## Design rules

- Do not silently drop source content.
- Do not invent missing text.
- Prefer a warning over a fake-perfect output.
- Keep EPUB output semantic and reader-friendly.
- Keep local/offline processing as the default.
- Keep changes small and testable.

## License

MIT. See `LICENSE`.
