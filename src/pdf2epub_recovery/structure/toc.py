"""Conservative table-of-contents detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pdf2epub_recovery.model import DocumentElement, DocumentTocEntry, QualityWarning, RawTextBlock

_LEADING_PAGE_RE = re.compile(r"^\s*(\d{1,4})\s+(.+?)\s*$")
_TRAILING_PAGE_RE = re.compile(r"^\s*(.+?)\s+(\d{1,4})\s*$")
_SECTION_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
_DOT_LEADER_RE = re.compile(r"(?:\s*\.\s*){4,}")
_TOC_TITLES = {"inhaltsverzeichnis", "inhalt", "contents", "table of contents"}


@dataclass(frozen=True)
class TocDetectionResult:
    text_blocks: list[RawTextBlock]
    toc_blocks: list[RawTextBlock]
    toc_elements: list[DocumentElement]
    warnings: list[QualityWarning] = field(default_factory=list)


def detect_toc_blocks(blocks: list[RawTextBlock]) -> TocDetectionResult:
    """Split likely table-of-contents pages from ordinary text blocks."""

    toc_page_indexes = _toc_page_indexes(blocks)
    if not toc_page_indexes:
        return TocDetectionResult(text_blocks=blocks, toc_blocks=[], toc_elements=[])

    text_blocks: list[RawTextBlock] = []
    toc_blocks: list[RawTextBlock] = []
    toc_elements: list[DocumentElement] = []
    warnings: list[QualityWarning] = []

    all_entries: list[DocumentTocEntry] = []
    all_source_blocks: list[RawTextBlock] = []
    first_toc_page: int | None = None

    for page_index in sorted(toc_page_indexes):
        page_blocks = [block for block in blocks if block.page_index == page_index]
        entries = [
            entry
            for block in page_blocks
            for entry in _toc_entries(block)
        ]
        if not entries:
            continue

        if first_toc_page is None:
            first_toc_page = page_index
        all_entries.extend(entries)
        all_source_blocks.extend(page_blocks)
        toc_blocks.extend(page_blocks)

    if all_entries and all_source_blocks:
        warning = QualityWarning(
            code="toc_links_not_resolved",
            severity="info",
            message=(
                "Table of contents was detected and cleaned, but EPUB links were not "
                "created because destination anchors are not resolved yet."
            ),
            page_index=first_toc_page,
        )
        warnings.append(warning)
        toc_elements.append(
            DocumentElement(
                element_id=f"toc-p{(first_toc_page or 0) + 1:04d}",
                element_type="toc",
                text="Inhaltsverzeichnis",
                source_refs=[block.source_ref() for block in all_source_blocks],
                confidence=0.75,
                warnings=[warning],
                toc_entries=all_entries,
            )
        )

    toc_block_ids = {block.block_id for block in toc_blocks}
    for block in blocks:
        if block.block_id not in toc_block_ids:
            text_blocks.append(block)

    return TocDetectionResult(
        text_blocks=text_blocks,
        toc_blocks=toc_blocks,
        toc_elements=toc_elements,
        warnings=warnings,
    )


def _toc_page_indexes(blocks: list[RawTextBlock]) -> set[int]:
    by_page: dict[int, list[RawTextBlock]] = {}
    for block in blocks:
        by_page.setdefault(block.page_index, []).append(block)

    page_indexes: set[int] = set()
    for page_index, page_blocks in by_page.items():
        has_title = any(_looks_like_toc_title(block.raw_text) for block in page_blocks[:5])
        entry_count = sum(len(_toc_entries(block)) for block in page_blocks)
        dot_leader_count = sum(1 for block in page_blocks if _DOT_LEADER_RE.search(block.raw_text))
        if (has_title and entry_count >= 3) or (entry_count >= 8 and dot_leader_count >= 3):
            page_indexes.add(page_index)

    for page_index in sorted(by_page):
        if page_index in page_indexes or page_index - 1 not in page_indexes:
            continue
        entry_count = sum(len(_toc_entries(block)) for block in by_page[page_index])
        if entry_count >= 3:
            page_indexes.add(page_index)
    return page_indexes


def _looks_like_toc_title(text: str) -> bool:
    normalized = " ".join(text.split()).strip().casefold()
    return normalized in _TOC_TITLES


def _toc_entries(block: RawTextBlock) -> list[DocumentTocEntry]:
    lines = [line.strip() for line in block.raw_text.splitlines() if line.strip()]
    if not lines:
        return []
    if len(lines) == 1 and _looks_like_toc_title(lines[0]):
        return []

    entries = _toc_entries_from_lines(lines)
    if entries:
        return entries

    page_label: str | None = None
    title_parts: list[str] = []

    if len(lines) >= 2 and lines[0].isdigit():
        page_label = lines[0]
        title_parts = lines[1:]
    elif len(lines) >= 2 and _DOT_LEADER_RE.search(lines[0]):
        page_label = _page_label_from_dot_leader(lines[0])
        title_parts = lines[1:]
    else:
        merged = " ".join(lines)
        without_dots = _DOT_LEADER_RE.sub(" ", merged)
        trailing = _TRAILING_PAGE_RE.match(without_dots)
        leading = _LEADING_PAGE_RE.match(without_dots)
        if trailing:
            title_parts = [trailing.group(1)]
            page_label = trailing.group(2)
        elif leading and _looks_like_numbered_heading(leading.group(2)):
            page_label = leading.group(1)
            title_parts = [leading.group(2)]
        else:
            return []

    title = _clean_title(" ".join(title_parts))
    if not title or not page_label:
        return []
    if len(title) > 140:
        return []
    return [DocumentTocEntry(title=title, level=_toc_level(title), page_label=page_label)]


def _toc_entries_from_lines(lines: list[str]) -> list[DocumentTocEntry]:
    entries: list[DocumentTocEntry] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _looks_like_toc_title(line):
            index += 1
            continue

        page_label: str | None = None
        title: str | None = None
        if index + 1 < len(lines) and _looks_like_section_number(line):
            next_without_dots = _DOT_LEADER_RE.sub(" ", lines[index + 1])
            next_trailing = _TRAILING_PAGE_RE.match(next_without_dots)
            if next_trailing:
                title = f"{line} {next_trailing.group(1)}"
                page_label = next_trailing.group(2)
                index += 2
            elif line.isdigit() and _looks_like_toc_title(lines[index + 1]) is False:
                page_label = line
                title = lines[index + 1]
                index += 2
            else:
                break
        elif (
            line.isdigit()
            and index + 1 < len(lines)
            and _looks_like_toc_title(lines[index + 1]) is False
        ):
            page_label = line
            title = lines[index + 1]
            index += 2
        else:
            without_dots = _DOT_LEADER_RE.sub(" ", line)
            trailing = _TRAILING_PAGE_RE.match(without_dots)
            leading = _LEADING_PAGE_RE.match(without_dots)
            if trailing:
                title = trailing.group(1)
                page_label = trailing.group(2)
                index += 1
            elif leading and _looks_like_numbered_heading(leading.group(2)):
                page_label = leading.group(1)
                title = leading.group(2)
                index += 1
            else:
                break

        cleaned = _clean_title(title or "")
        if not cleaned or not page_label or len(cleaned) > 140:
            break
        entries.append(
            DocumentTocEntry(title=cleaned, level=_toc_level(cleaned), page_label=page_label)
        )

    return entries if len(entries) >= 2 else []


def _page_label_from_dot_leader(text: str) -> str | None:
    match = re.search(r"(\d{1,4})\s*$", text)
    return match.group(1) if match else None


def _clean_title(text: str) -> str:
    cleaned = _DOT_LEADER_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _looks_like_numbered_heading(text: str) -> bool:
    return bool(_SECTION_RE.match(text.strip()))


def _looks_like_section_number(text: str) -> bool:
    return bool(re.match(r"^\d+(?:\.\d+)*\.?$", text.strip()))


def _toc_level(title: str) -> int:
    stripped = title.strip()
    match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", stripped)
    if match:
        return min(6, match.group(1).count(".") + 1)
    return 2 if not _SECTION_RE.match(stripped) else 1
