# Decision 0001 — Repository name

Date: 2026-05-10

## Decision

Use `pdf2epub-recovery` as the repository and Python package name for now.

Use **PDF2EPUB Converter** as the visible product name in user-facing UI and documentation.

## Reason

The product is a converter. The implementation still uses "recovery" internally because useful PDF-to-EPUB conversion requires recovering document structure from PDFs before rendering EPUB.

Keeping the repository/package name stable avoids a broad rename across imports, CLI entry points, tests, and local documentation while the MVP is still moving quickly.

The repository name is:
- direct
- searchable
- technically accurate
- better for GitHub discovery than a pure brand name

## Alternatives considered

- `ReflowForge`: good later product name, less clear as GitHub repo.
- `pdf2book`: broader, but less precise.
- `epub-rebuilder`: good conceptually, less clear that PDF is the input.
