"""Conservative page artifact detection and removal."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from pdf2epub_recovery.model import RawTextBlock, RemovedArtifact

_PAGE_NUMBER_RE = re.compile(
    r"^(?:(?:page|seite|p\.|s\.)\s*)?(\d{1,5})(?:\s*(?:of|von|/)\s*\d{1,5})?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ArtifactRemovalResult:
    kept_blocks: list[RawTextBlock]
    removed_artifacts: list[RemovedArtifact]


def remove_page_artifacts(
    blocks: list[RawTextBlock], keep_artifacts: bool = False
) -> ArtifactRemovalResult:
    """Remove only very safe page numbers and repeated headers/footers."""

    if keep_artifacts or not blocks:
        return ArtifactRemovalResult(kept_blocks=blocks, removed_artifacts=[])

    artifacts_by_block_id: dict[str, RemovedArtifact] = {}
    page_count = len({block.page_index for block in blocks})
    if page_count < 2:
        return ArtifactRemovalResult(kept_blocks=blocks, removed_artifacts=[])

    for artifact in _detect_page_numbers(blocks):
        artifacts_by_block_id[artifact.source_ref.block_id] = artifact

    for artifact in _detect_repeated_margin_text(blocks):
        artifacts_by_block_id.setdefault(artifact.source_ref.block_id, artifact)

    kept = [block for block in blocks if block.block_id not in artifacts_by_block_id]
    removed = list(artifacts_by_block_id.values())
    removed.sort(key=lambda item: (item.source_ref.page_index, item.source_ref.bbox.y0))
    return ArtifactRemovalResult(kept_blocks=kept, removed_artifacts=removed)


def _detect_page_numbers(blocks: list[RawTextBlock]) -> list[RemovedArtifact]:
    numeric_candidates: list[tuple[RawTextBlock, int]] = []
    for block in blocks:
        text = _single_line(block.raw_text)
        page_number = _page_number_from_text(text)
        if page_number is not None and _in_margin(block):
            numeric_candidates.append((block, page_number))

    if len(numeric_candidates) < 2:
        return []

    numeric_candidates.sort(key=lambda item: item[0].page_index)
    pages = [block.page_index for block, _number in numeric_candidates]
    numbers = [number for _block, number in numeric_candidates]

    offsets = Counter(number - page for page, number in zip(pages, numbers, strict=True))
    dominant_offset, dominant_count = offsets.most_common(1)[0]
    follows_page_index = sum(
        1 for page, number in zip(pages, numbers, strict=True) if number == page + 1
    )
    is_consecutive = all(
        numbers[index] + 1 == numbers[index + 1] for index in range(len(numbers) - 1)
    )
    follows_constant_offset = dominant_count >= max(3, len(numeric_candidates) // 2)
    if follows_page_index < 2 and not is_consecutive and not follows_constant_offset:
        return []

    if follows_constant_offset and follows_page_index < 2 and not is_consecutive:
        numeric_candidates = [
            (block, number)
            for block, number in numeric_candidates
            if number - block.page_index == dominant_offset
        ]

    return [
        RemovedArtifact(
            artifact_id=f"a-page-number-{block.block_id}",
            artifact_type="page_number",
            text=_single_line(block.raw_text),
            source_ref=block.source_ref(),
            reason="Margin text follows a repeated page-number sequence.",
            confidence=0.95,
        )
        for block, _number in numeric_candidates
    ]


def _detect_repeated_margin_text(blocks: list[RawTextBlock]) -> list[RemovedArtifact]:
    grouped: dict[tuple[str, str], list[RawTextBlock]] = defaultdict(list)
    for block in blocks:
        zone = _margin_zone(block)
        if zone is None:
            continue
        text = _single_line(block.raw_text)
        if not text or len(text) > 120 or _page_number_from_text(text) is not None:
            continue
        grouped[(zone, _normalize_repeated_text(text))].append(block)

    artifacts: list[RemovedArtifact] = []
    for (zone, _text_key), candidates in grouped.items():
        page_counts = Counter(block.page_index for block in candidates)
        if len(page_counts) < 2:
            continue
        if zone in {"left", "right"} and len(page_counts) < 3:
            continue
        artifact_type = _artifact_type_for_zone(zone)
        for block in candidates:
            artifacts.append(
                RemovedArtifact(
                    artifact_id=f"a-{artifact_type}-{block.block_id}",
                    artifact_type=artifact_type,
                    text=_single_line(block.raw_text),
                    source_ref=block.source_ref(),
                    reason=f"Repeated {zone} margin text appears on multiple pages.",
                    confidence=0.9,
                )
            )
    return artifacts


def _single_line(text: str) -> str:
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _normalize_repeated_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _page_number_from_text(text: str) -> int | None:
    match = _PAGE_NUMBER_RE.match(text.strip())
    if match is None:
        return None
    return int(match.group(1))


def _margin_zone(block: RawTextBlock) -> str | None:
    top_limit = block.page_height * 0.12
    bottom_limit = block.page_height * 0.88
    left_limit = block.page_width * 0.22
    right_limit = block.page_width * 0.78
    if block.bbox.y1 <= top_limit:
        return "top"
    if block.bbox.y0 >= bottom_limit:
        return "bottom"
    if block.bbox.x1 <= left_limit:
        return "left"
    if block.bbox.x0 >= right_limit:
        return "right"
    return None


def _in_margin(block: RawTextBlock) -> bool:
    return _margin_zone(block) is not None


def _artifact_type_for_zone(zone: str) -> str:
    if zone == "top":
        return "header"
    if zone == "bottom":
        return "footer"
    return "margin_note"
