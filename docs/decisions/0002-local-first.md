# Decision 0002 — Local-first processing

Date: 2026-05-10

## Decision

The tool should work locally by default.

## Reason

Users may process books, contracts, manuals, scripts, research, and private files. PDF conversion often involves sensitive documents.

## Implications

- No cloud service is required for MVP.
- Optional external engines may be added later.
- Any remote/LLM-assisted mode must be explicit.
- Local debug outputs must avoid accidental data leaks when shared.
