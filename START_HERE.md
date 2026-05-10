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

MVP 1 is implemented:
- native-text PDF profiling and extraction
- conservative page artifact removal
- simple reading order, conservative clear two-column fallback, and paragraph reconstruction
- basic EPUB output with simple embedded image preservation
- obvious text-table detection with readable EPUB fallback
- debug JSON for removed artifacts, ordered blocks, kept margin blocks, and table fallbacks
- JSON quality report
- local web UI with progress log, drag-and-drop upload, and explained options

Still intentionally unsupported:
- OCR for scanned PDFs
- complex table reconstruction beyond simple text-table fallback
- masked, transparent, or unusual image preservation cases
- reliable reading order for complex multi-column layouts
