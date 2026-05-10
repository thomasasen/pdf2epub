# AGENTS.md — pdf2epub-recovery

Purpose: stable project instructions for Codex and other coding agents.

Keep this file concise. Put long research, raw logs, and benchmark results into `docs/`.
Update this file when project rules, architecture, validation, or scope changes.

## Project identity

Repository name: `pdf2epub-recovery`

Short description:
> Local-first PDF-to-EPUB document recovery engine focused on clean reading order, repaired paragraphs, removed page artifacts, preserved tables/images, and honest quality reports.

This is not a naive converter. The project is a recovery pipeline.

```text
PDF
→ document profiling
→ layout-aware extraction
→ block normalization
→ page artifact detection/removal
→ reading-order resolution
→ paragraph reconstruction
→ table/image/footnote handling
→ document IR
→ EPUB rendering
→ validation
→ quality report
```

## Core user problems

Solve these first:
- Page numbers inside EPUB text.
- Repeated headers and footers inside EPUB text.
- Broken line wrapping.
- Bad paragraph reconstruction.
- Wrong reading order.
- Destroyed tables.
- Lost or misplaced images.
- EPUB output without honest warnings.
- OCR uncertainty hidden from the user.

## Product principle

The tool must be honest.

If a PDF can be converted well, produce a clean EPUB.
If only parts are reliable, produce an EPUB with warnings.
If EPUB is the wrong output, say so and recommend an optimized PDF workflow instead.

Never pretend that a poor conversion is good.

## Current scope

Current project status: MVP 1 implemented plus first structure-recovery polish.

Primary target:
> One-column, text-centric PDFs with native embedded text, simple images, simple tables, simple PDF table-of-contents pages, simple highlighted callouts, and repeated page artifacts.

Early non-goals:
- Perfect conversion of every PDF.
- Pixel-perfect PDF layout reproduction.
- Comics, manga, magazines, brochures.
- DRM-protected PDFs.
- Complex forms.
- Full MathML reconstruction.
- Full scan/OCR workflow.
- Cloud-only processing.

## Default stack

Prefer Python.

Current bootstrap stack:
- Python 3.11+
- `src/` layout
- CLI-first
- local-first
- pytest tests
- ruff-compatible formatting
- typed dataclasses where useful
- no heavy runtime dependency until a phase needs it

Candidate future dependencies:
- PyMuPDF for PDF text/word/block geometry.
- Marker for structured document extraction.
- Docling for document understanding and table/layout extraction.
- OCRmyPDF/Tesseract/PaddleOCR for scans.
- EPUBCheck for EPUB validation.

Do not add heavy dependencies without a task-specific reason.

## Codex operating rules

1. Read relevant files before editing.
2. Make the smallest safe change.
3. Do not rewrite broad areas unless requested.
4. Preserve behavior unless the task explicitly changes it.
5. Prefer explicit code over clever code.
6. Keep public APIs stable unless the task changes them.
7. Never silently drop extracted content.
8. Never invent source text.
9. Every lossy decision must appear in the quality report.
10. Keep diffs reviewable.

## Work format for non-trivial tasks

Before implementation, provide:
- files likely touched
- intended approach
- risks
- validation to run

After implementation, report:
- what changed
- why it changed
- what was validated
- what was not validated
- remaining risk

## Token discipline

Rules:
- Keep `AGENTS.md` short and stable.
- Put detailed planning in `docs/`.
- Do not paste huge logs into prompts.
- Summarize logs and reference files.
- Avoid broad refactors.
- Prefer one vertical slice per task.
- If Codex repeats a mistake, add one short rule here.

Recommended task prompt shape:

```text
Goal:
<one concrete change>

Context:
<relevant files and current behavior>

Constraints:
- smallest safe change
- no unrelated behavior changes
- update tests

Done when:
- tests pass
- summary states changed / validated / unverified
```

## Definition of done

A task is done only when:
- change is in the correct source layer
- validation ran or blocker is documented
- tests were added or updated when behavior changed
- generated EPUB behavior is validated when EPUB output is touched
- quality report reflects important uncertainty
- final summary includes remaining risks

## Core invariants

1. Source text fidelity beats prettiness.
2. Do not remove content unless classified as artifact with evidence.
3. Removed content must be counted and traceable.
4. Paragraph merging must preserve sentence order.
5. Hyphenation repair must be conservative.
6. Table fallback is better than destroyed tables.
7. Reading-order uncertainty must be reported.
8. EPUB XHTML must be simple and semantic.
9. CSS must support reader-controlled font sizes.
10. The tool works locally by default.

## Current architecture

```text
src/pdf2epub_recovery/
  cli.py
  model.py
  profiling/
  extraction/
  cleaning/
  reading_order/
  structure/
  rendering/
  validation/
docs/
  architecture/
  decisions/
tests/
  fixtures/
```

Grow structure only when needed.

## Current next step

Next slice:
- resolve preserved PDF table-of-contents entries to safe internal EPUB links
- replace document-specific table heuristics with more general layout evidence
- keep multi-column recovery conservative
- keep README honest about unsupported OCR and complex layouts

## Change log

- 2026-05-10: Initial Codex agent instructions created.
- 2026-05-10: MVP 1 vertical slice implemented.
- 2026-05-10: Added first structure-recovery polish for tables, PDF TOC, callouts, lists, links, and EPUB packaging.
