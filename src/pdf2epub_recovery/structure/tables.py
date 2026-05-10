"""Conservative table-like text block detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pdf2epub_recovery.model import DocumentElement, QualityWarning, RawTextBlock

_MULTISPACE_RE = re.compile(r"\s{2,}")


@dataclass(frozen=True)
class TableDetectionResult:
    text_blocks: list[RawTextBlock]
    table_blocks: list[RawTextBlock]
    table_elements: list[DocumentElement]
    warnings: list[QualityWarning] = field(default_factory=list)


def detect_table_like_blocks(blocks: list[RawTextBlock]) -> TableDetectionResult:
    """Split obvious text-table blocks from ordinary text blocks."""

    text_blocks: list[RawTextBlock] = []
    table_blocks: list[RawTextBlock] = []
    table_elements: list[DocumentElement] = []
    warnings: list[QualityWarning] = []

    for block in blocks:
        if _is_table_like_text(block.raw_text):
            table_blocks.append(block)
            warning = QualityWarning(
                code="table_fallback_used",
                message=(
                    "Possible table-like text was preserved as a preformatted fallback; "
                    "full table reconstruction is not implemented."
                ),
                page_index=block.page_index,
            )
            warnings.append(warning)
            table_elements.append(
                DocumentElement(
                    element_id=f"table-{block.block_id}",
                    element_type="table",
                    text=_normalize_table_text(block.raw_text),
                    source_refs=[block.source_ref()],
                    confidence=0.65,
                    warnings=[warning],
                )
            )
            continue
        text_blocks.append(block)

    return TableDetectionResult(
        text_blocks=text_blocks,
        table_blocks=table_blocks,
        table_elements=table_elements,
        warnings=warnings,
    )


def _is_table_like_text(text: str) -> bool:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    column_counts = [_column_count(line) for line in lines]
    table_rows = [count for count in column_counts if count >= 2]
    if len(table_rows) < 2:
        return False

    most_common_count = max(set(table_rows), key=table_rows.count)
    repeated_count_rows = sum(1 for count in table_rows if count == most_common_count)
    return repeated_count_rows >= 2


def _column_count(line: str) -> int:
    stripped = line.strip()
    if "\t" in stripped:
        return len([part for part in stripped.split("\t") if part.strip()])
    if "|" in stripped:
        return len([part for part in stripped.strip("|").split("|") if part.strip()])
    parts = [part for part in _MULTISPACE_RE.split(stripped) if part.strip()]
    return len(parts)


def _normalize_table_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)
