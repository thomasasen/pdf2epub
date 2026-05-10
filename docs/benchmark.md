# Benchmark Plan

The benchmark measures reading quality, not only whether a file was produced.

## Fixture categories

Use small, legally safe fixtures.

- one-column text PDF
- text PDF with page numbers
- text PDF with running headers/footers
- German hyphenation sample
- simple table PDF
- table with wrapped cells
- table of contents with dot leaders and page labels
- highlighted callout/sidebar sample
- bullet list sample
- plain web address sample
- image-only scan sample
- two-column article sample

## What to measure

- Did page numbers disappear?
- Did repeated headers/footers disappear?
- Did paragraphs look natural?
- Did reading order make sense?
- Did tables remain readable?
- Did table headers and cell boundaries remain understandable?
- Did the table of contents stop leaking dot leaders into the EPUB text?
- Were callouts preserved without turning ordinary paragraphs into boxes?
- Did bullet lists remain stacked and readable?
- Were web addresses clickable?
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
