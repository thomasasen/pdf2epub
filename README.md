# pdf2epub-recovery

A local-first PDF-to-EPUB document recovery engine.

The goal is not to build another naive PDF converter. The goal is to recover enough document structure to produce readable EPUB files and to report uncertainty honestly.

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

This repository has its first MVP vertical slice.

Implemented MVP 1 scope:
- Real PDF profiling with PyMuPDF.
- Native text block extraction with geometry and provenance.
- Conservative removal of repeated page numbers, headers, and footers.
- Simple one-column reading order.
- Basic paragraph reconstruction and conservative dehyphenation.
- Basic reflowable EPUB output with EbookLib.
- Reader-friendly EPUB CSS and basic paragraph spacing.
- Simple embedded image preservation in EPUB output.
- Image preservation counts and unsupported-image warnings in reports.
- Obvious text-table detection with preformatted EPUB fallback.
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

Known limitations:
- OCR is not implemented.
- Image-only/scanned pages are reported, not recovered.
- Complex tables are not reconstructed; simple text tables use a readable fallback.
- Masked, transparent, transformed, or unusual image encodings may be reported but not preserved.
- Multi-column documents may warn and can have imperfect reading order.
- EPUBCheck validation is optional and only runs if an `epubcheck` executable is configured on `PATH`.

## Why this project exists

Most PDF-to-EPUB workflows fail because PDF is page-position based while EPUB is structured, reflowable web content. A good tool must therefore recover document structure before rendering EPUB.

Target pipeline:

```text
PDF
-> profile
-> extract blocks with geometry
-> remove safe page artifacts
-> resolve reading order
-> rebuild paragraphs
-> preserve simple images or report unsupported cases
-> preserve obvious text tables as fallback blocks
-> render EPUB
-> report quality
```

Future phases will add stronger table/image handling, better multi-column recovery, optional validation integration, and later OCR/multi-engine workflows.

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
- EPUB and report download links when conversion finishes.

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
