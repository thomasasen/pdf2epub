# Benchmark Plan

The benchmark measures reading quality, not only whether a file was produced.

## Fixture categories

Use small, legally safe fixtures.

- one-column text PDF
- text PDF with page numbers
- text PDF with running headers/footers
- German hyphenation sample
- simple table PDF
- image-only scan sample
- two-column article sample

## What to measure

- Did page numbers disappear?
- Did repeated headers/footers disappear?
- Did paragraphs look natural?
- Did reading order make sense?
- Did tables remain readable?
- Were images preserved?
- Did EPUBCheck pass?
- Were warnings useful?

## Snapshot strategy

Keep snapshots small:
- profile JSON
- raw extraction JSON
- document IR excerpt
- XHTML snippet
- quality report JSON

Do not add large copyrighted PDFs to the repository.
