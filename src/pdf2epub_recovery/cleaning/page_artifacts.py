"""Conservative page artifact detection and removal."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from pdf2epub_recovery.model import RawTextBlock, RemovedArtifact

_PAGE_NUMBER_RE = re.compile(r"^(?:page\s*)?(\d{1,5})$", re.IGNORECASE)


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
        match = _PAGE_NUMBER_RE.match(text)
        if match and _in_margin(block):
            numeric_candidates.append((block, int(match.group(1))))

    if len(numeric_candidates) < 2:
        return []

    numeric_candidates.sort(key=lambda item: item[0].page_index)
    pages = [block.page_index for block, _number in numeric_candidates]
    numbers = [number for _block, number in numeric_candidates]

    follows_page_index = sum(
        1 for page, number in zip(pages, numbers, strict=True) if number == page + 1
    )
    is_consecutive = all(
        numbers[index] + 1 == numbers[index + 1] for index in range(len(numbers) - 1)
    )
    if follows_page_index < 2 and not is_consecutive:
        return []

    return [
        RemovedArtifact(
            artifact_id=f"a-page-number-{block.block_id}",
            artifact_type="page_number",
            text=_single_line(block.raw_text),
            source_ref=block.source_ref(),
            reason="Numeric margin text follows a repeated page-number sequence.",
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
        if not text or len(text) > 120 or _PAGE_NUMBER_RE.match(text):
            continue
        grouped[(zone, _normalize_repeated_text(text))].append(block)

    artifacts: list[RemovedArtifact] = []
    for (zone, _text_key), candidates in grouped.items():
        page_counts = Counter(block.page_index for block in candidates)
        if len(page_counts) < 2:
            continue
        artifact_type = "header" if zone == "top" else "footer"
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


def _margin_zone(block: RawTextBlock) -> str | None:
    top_limit = block.page_height * 0.12
    bottom_limit = block.page_height * 0.88
    if block.bbox.y1 <= top_limit:
        return "top"
    if block.bbox.y0 >= bottom_limit:
        return "bottom"
    return None


def _in_margin(block: RawTextBlock) -> bool:
    return _margin_zone(block) is not None
