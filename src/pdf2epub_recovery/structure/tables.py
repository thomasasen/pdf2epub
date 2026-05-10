"""Conservative table-like text block detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pdf2epub_recovery.model import BBox, DocumentElement, DocumentTable, QualityWarning, RawTextBlock

_MULTISPACE_RE = re.compile(r"\s{2,}")
_DOT_LEADER_RE = re.compile(r"^[\s.]+$")
_Delimiter = Literal["multispace", "pipe", "tab"]
_KNOWN_WRAPPED_TERMS = {
    ("Decision", "Criteria"),
    ("Decision", "Process"),
    ("Economic", "Buyer"),
    ("Identify", "Pain"),
    ("No", "Decision"),
    ("Paper", "Process"),
}


@dataclass(frozen=True)
class TableDetectionResult:
    text_blocks: list[RawTextBlock]
    table_blocks: list[RawTextBlock]
    table_elements: list[DocumentElement]
    warnings: list[QualityWarning] = field(default_factory=list)


@dataclass(frozen=True)
class _RowBand:
    blocks: list[RawTextBlock]

    @property
    def page_index(self) -> int:
        return self.blocks[0].page_index

    @property
    def bbox(self) -> BBox:
        return _combined_bbox(self.blocks)


def detect_table_like_blocks(blocks: list[RawTextBlock]) -> TableDetectionResult:
    """Split obvious text-table blocks from ordinary text blocks."""

    text_blocks: list[RawTextBlock] = []
    sequence_result = _detect_geometry_table_runs(blocks)
    table_blocks = list(sequence_result.table_blocks)
    table_elements = list(sequence_result.table_elements)
    warnings = list(sequence_result.warnings)
    consumed_block_ids = {block.block_id for block in sequence_result.table_blocks}

    for block in blocks:
        if block.block_id in consumed_block_ids:
            continue

        parsed_table = _parse_consistently_delimited_table(block.raw_text)
        if parsed_table is not None:
            table_blocks.append(block)
            table_elements.append(
                DocumentElement(
                    element_id=f"table-{block.block_id}",
                    element_type="table",
                    text=_normalize_table_text(block.raw_text),
                    source_refs=[block.source_ref()],
                    confidence=0.82,
                    table=parsed_table,
                )
            )
            continue

        if _is_table_like_text(block.raw_text):
            table_blocks.append(block)
            warning = QualityWarning(
                code="table_fallback_used",
                message=(
                    "Possible table-like text was preserved as a preformatted fallback "
                    "because it was not consistently delimited."
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


def _detect_geometry_table_runs(blocks: list[RawTextBlock]) -> TableDetectionResult:
    row_bands = _row_bands(blocks)
    table_blocks: list[RawTextBlock] = []
    table_elements: list[DocumentElement] = []
    warnings: list[QualityWarning] = []
    consumed_block_ids: set[str] = set()

    index = 0
    while index < len(row_bands):
        run = _table_like_band_run(row_bands, index)
        if run is None:
            index += 1
            continue

        run_blocks = [block for band in run for block in band.blocks]
        if any(block.block_id in consumed_block_ids for block in run_blocks):
            index += 1
            continue

        warning = QualityWarning(
            code="table_fallback_used",
            message=(
                "Possible block-structured table was preserved as a preformatted fallback "
                "because reliable cell reconstruction is not implemented yet."
            ),
            page_index=run[0].page_index,
        )
        warnings.append(warning)
        table_blocks.extend(run_blocks)
        consumed_block_ids.update(block.block_id for block in run_blocks)
        first_block = run_blocks[0]
        table_elements.append(
            DocumentElement(
                element_id=f"table-{first_block.block_id}-run",
                element_type="table",
                text=_format_row_band_table(run),
                source_refs=[block.source_ref() for block in run_blocks],
                confidence=0.6,
                warnings=[warning],
            )
        )
        index += len(run)

    return TableDetectionResult(
        text_blocks=[],
        table_blocks=table_blocks,
        table_elements=table_elements,
        warnings=warnings,
    )


def _row_bands(blocks: list[RawTextBlock]) -> list[_RowBand]:
    bands: list[_RowBand] = []
    current: list[RawTextBlock] = []

    for block in blocks:
        if current and _belongs_to_current_row_band(current[-1], block):
            current.append(block)
            continue

        if current:
            bands.append(_RowBand(current))
        current = [block]

    if current:
        bands.append(_RowBand(current))
    return bands


def _belongs_to_current_row_band(previous: RawTextBlock, block: RawTextBlock) -> bool:
    if previous.page_index != block.page_index:
        return False
    if _vertical_overlap(previous.bbox, block.bbox) >= 0.35:
        return True
    return abs(previous.bbox.y0 - block.bbox.y0) <= 8 and abs(previous.bbox.y1 - block.bbox.y1) <= 12


def _vertical_overlap(left: BBox, right: BBox) -> float:
    overlap = min(left.y1, right.y1) - max(left.y0, right.y0)
    if overlap <= 0:
        return 0.0
    smaller_height = max(1.0, min(left.height, right.height))
    return overlap / smaller_height


def _table_like_band_run(row_bands: list[_RowBand], start: int) -> list[_RowBand] | None:
    first = row_bands[start]
    if not _is_tabular_band(first):
        return None

    run = [first]
    for band in row_bands[start + 1 :]:
        if band.page_index != first.page_index:
            break
        if not _is_tabular_band(band):
            break
        if not _is_plausible_table_neighbor(run[-1], band):
            break
        run.append(band)

    if len(run) < 3:
        return None
    if sum(1 for band in run if len(band.blocks) > 1) == 0 and not _has_stable_left_edge(run):
        return None
    return run


def _is_tabular_band(band: _RowBand) -> bool:
    if len(band.blocks) >= 2:
        return True

    if band.bbox.height > 36:
        return False
    text = band.blocks[0].raw_text.strip()
    if _looks_like_non_table_text(text):
        return False
    lines = _meaningful_lines(text)
    if not 2 <= len(lines) <= 6:
        return False
    if any(len(line) > 90 for line in lines):
        return False
    return True


def _looks_like_non_table_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    lines = _meaningful_lines(stripped)
    if (
        len(lines) >= 2
        and len(lines[0].split()) >= 4
        and lines[1][:1].islower()
    ):
        return True
    if len(lines) >= 2 and lines[0].isdigit() and re.match(r"^\d+\.", lines[1]):
        return True
    if stripped.startswith(("•", "-", "–")):
        return True
    if _DOT_LEADER_RE.match(stripped.replace("\n", "")):
        return True
    if stripped.count(".") > 12 and len(stripped) > 40:
        return True
    return False


def _is_plausible_table_neighbor(previous: _RowBand, band: _RowBand) -> bool:
    if band.bbox.y0 < previous.bbox.y0:
        return False
    vertical_gap = band.bbox.y0 - previous.bbox.y1
    if vertical_gap > 32:
        return False
    left_delta = abs(band.bbox.x0 - previous.bbox.x0)
    if left_delta <= 32:
        return True
    return len(previous.blocks) > 1 and len(band.blocks) > 1


def _has_stable_left_edge(run: list[_RowBand]) -> bool:
    left_edges = [round(band.bbox.x0 / 10) * 10 for band in run]
    most_common = max(set(left_edges), key=left_edges.count)
    return left_edges.count(most_common) >= max(3, len(run) - 1)


def _format_row_band_table(run: list[_RowBand]) -> str:
    header = _normalize_header_cells(_row_band_cells(run[0]))
    expected_column_count = len(header) if len(header) >= 2 else None
    rows = [header]
    rows.extend(_row_band_cells(band, expected_column_count) for band in run[1:])
    return "\n".join(" | ".join(cells) for cells in rows)


def _row_band_cells(band: _RowBand, expected_column_count: int | None = None) -> list[str]:
    if len(band.blocks) == 1:
        lines = _merge_wrapped_fragments(_meaningful_lines(band.blocks[0].raw_text))
        return _split_lines_to_cells(lines, expected_column_count)

    cells: list[str] = []
    sorted_blocks = sorted(band.blocks, key=lambda block: block.bbox.x0)
    for index, block in enumerate(sorted_blocks):
        lines = _meaningful_lines(block.raw_text)
        remaining_blocks = len(sorted_blocks) - index - 1
        slots = _available_slots_for_block(
            expected_column_count,
            current_cell_count=len(cells),
            remaining_blocks=remaining_blocks,
        )
        cells.extend(_split_lines_to_cells(lines, slots))
    return cells


def _normalize_header_cells(cells: list[str]) -> list[str]:
    return _merge_wrapped_fragments(cells)


def _cell_text(text: str) -> str:
    return _join_cell_lines(_meaningful_lines(text))


def _available_slots_for_block(
    expected_column_count: int | None,
    *,
    current_cell_count: int,
    remaining_blocks: int,
) -> int | None:
    if expected_column_count is None:
        return None
    return max(1, expected_column_count - current_cell_count - remaining_blocks)


def _split_lines_to_cells(lines: list[str], max_cells: int | None) -> list[str]:
    if not lines:
        return []
    if max_cells is None or len(lines) <= max_cells:
        return lines
    if max_cells == 3:
        status_index = _status_cell_index(lines)
        if status_index == 1:
            return [lines[0], lines[1], _join_cell_lines(lines[2:])]
        if status_index == 2:
            return [_join_cell_lines(lines[:2]), lines[2], _join_cell_lines(lines[3:])]
    if max_cells == 1:
        return [_join_cell_lines(lines)]
    return [*lines[: max_cells - 1], _join_cell_lines(lines[max_cells - 1 :])]


def _status_cell_index(lines: list[str]) -> int | None:
    status_values = {
        "hoch",
        "mittel",
        "unsicher",
        "offen",
        "teilweise",
        "unscharf",
        "rot/gelb/grün",
        "rot/gelb/gruen",
        "rot/gelb/grÃ¼n",
    }
    for index, line in enumerate(lines):
        if line.lower() in status_values:
            return index
    return None


def _merge_wrapped_fragments(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if merged and (merged[-1], line) in _KNOWN_WRAPPED_TERMS:
            merged[-1] = f"{merged[-1]} {line}"
            continue
        if (
            merged
            and len(line) <= 2
            and merged[-1][-1:].islower()
            and line[:1].islower()
        ):
            merged[-1] += line
            continue
        merged.append(line)
    return merged


def _join_cell_lines(lines: list[str]) -> str:
    if not lines:
        return ""

    text = lines[0]
    for line in lines[1:]:
        if text.endswith("-"):
            text = text[:-1] + line
            continue
        previous_word = text.rsplit(maxsplit=1)[-1]
        previous_fragment = previous_word.rsplit("/", 1)[-1]
        next_word = line.split(maxsplit=1)[0]
        if (
            text[-1:].islower()
            and line[:1].islower()
            and (len(previous_fragment) == 1 or len(next_word) == 1)
        ):
            text += line
            continue
        text += f" {line}"
    return text


def _meaningful_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _combined_bbox(blocks: list[RawTextBlock]) -> BBox:
    return BBox(
        min(block.bbox.x0 for block in blocks),
        min(block.bbox.y0 for block in blocks),
        max(block.bbox.x1 for block in blocks),
        max(block.bbox.y1 for block in blocks),
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


def _parse_consistently_delimited_table(text: str) -> DocumentTable | None:
    lines = [line.rstrip() for line in _normalize_table_text(text).splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    delimiter = _detect_consistent_delimiter(lines)
    if delimiter is None:
        return None

    rows = [_split_row(line, delimiter) for line in lines]
    if any(row is None for row in rows):
        return None

    table_rows = [row for row in rows if row is not None]
    column_count = len(table_rows[0])
    if column_count < 2:
        return None
    if any(len(row) != column_count for row in table_rows):
        return None
    if any(not all(cell for cell in row) for row in table_rows):
        return None

    return DocumentTable(rows=table_rows, source_format=delimiter)


def _detect_consistent_delimiter(lines: list[str]) -> _Delimiter | None:
    candidates: list[_Delimiter] = []
    if all("\t" in line for line in lines):
        candidates.append("tab")
    if all("|" in line for line in lines):
        candidates.append("pipe")
    if all(_MULTISPACE_RE.search(line) for line in lines):
        candidates.append("multispace")

    for delimiter in candidates:
        counts = [len(_split_row(line, delimiter) or []) for line in lines]
        if len(set(counts)) == 1 and counts[0] >= 2:
            return delimiter
    return None


def _split_row(line: str, delimiter: _Delimiter) -> list[str] | None:
    stripped = line.strip()
    if delimiter == "tab":
        cells = [part.strip() for part in stripped.split("\t")]
    elif delimiter == "pipe":
        cells = [part.strip() for part in stripped.strip("|").split("|")]
    else:
        cells = [part.strip() for part in _MULTISPACE_RE.split(stripped)]

    if len(cells) < 2:
        return None
    return cells


def _normalize_table_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)
