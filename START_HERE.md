# START HERE

Use this order for local development.

## 1. Install

From the repository root:

```powershell
python -m pip install -e ".[dev]"
```

## 2. Start the web interface

```powershell
python -m pdf2epub_recovery web
```

Open:

```text
http://127.0.0.1:8765/
```

Stop the server with `Ctrl+C` in the terminal where it is running.

If the port is already in use:

```powershell
python -m pdf2epub_recovery web --port 8770
```

## 3. Use the CLI directly

```powershell
python -m pdf2epub_recovery --help
python -m pdf2epub_recovery profile input.pdf --out profile.json
python -m pdf2epub_recovery extract input.pdf --out debug-extraction.json
python -m pdf2epub_recovery convert input.pdf --out book.epub --report book.report.json
python -m pdf2epub_recovery convert input.pdf --out book.epub --debug-dir debug
```

The installed console script may also work when it is on your `PATH`:

```powershell
pdf2epub-recovery web
```

On Windows, prefer the `python -m pdf2epub_recovery ...` form if the script is not recognized.

## 4. Validate changes

```powershell
python -m pytest
python -m ruff check .
```

## Current status

MVP 1 plus the first converter polish is implemented:
- native-text PDF profiling and extraction
- conservative page artifact removal
- simple reading order, conservative clear two-column fallback, and paragraph reconstruction
- reflowable EPUB output with OPF, NAV, NCX fallback, CSS, and simple embedded image preservation
- obvious text-table detection with semantic XHTML tables when reliable and readable fallbacks otherwise
- PDF table-of-contents detection with dot-leader cleanup
- simple callout/sidebar conversion from detectable filled rectangles
- bullet-list rendering and clickable `http://` / `https://` links
- debug JSON for removed artifacts, ordered blocks, kept margin blocks, table fallbacks, images, and full document IR
- JSON quality report
- local web UI with progress log, drag-and-drop upload, explained options, quality summary, warning list, and debug ZIP download

Still intentionally unsupported:
- OCR for scanned PDFs
- complex table reconstruction beyond the current semantic/fallback heuristics
- resolved internal links from preserved PDF table-of-contents entries
- masked, transparent, or unusual image preservation cases
- reliable reading order for complex multi-column layouts
