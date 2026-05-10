"""Simple paragraph reconstruction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pdf2epub_recovery.model import DocumentElement, Paragraph, QualityWarning, RawTextBlock

_SENTENCE_END_RE = re.compile(r"[.!?:;]['\")\]]?$")


@dataclass(frozen=True)
class ParagraphReconstructionResult:
    paragraphs: list[Paragraph]
    hyphenation_repairs: int
    line_wrap_repairs: int
    warnings: list[QualityWarning]


def reconstruct_paragraphs(
    blocks: list[RawTextBlock], dehyphenate: bool = True
) -> ParagraphReconstructionResult:
    """Build readable paragraphs from ordered raw text blocks."""

    pending: Paragraph | None = None
    paragraphs: list[Paragraph] = []
    hyphenation_repairs = 0
    line_wrap_repairs = 0

    for block in blocks:
        segments = _split_block_paragraphs(block.raw_text)
        for segment_index, segment in enumerate(segments):
            text, block_hyphenations, block_line_wraps = _merge_block_lines(segment, dehyphenate)
            if not text:
                continue

            hyphenation_repairs += block_hyphenations
            line_wrap_repairs += block_line_wraps
            current = Paragraph(
                element_id="",
                text=text,
                source_refs=[block.source_ref()],
                confidence=0.9,
            )

            if pending and segment_index == 0 and _can_merge_blocks(pending, block):
                pending = Paragraph(
                    element_id="",
                    text=f"{pending.text} {current.text}",
                    source_refs=[*pending.source_refs, *current.source_refs],
                    confidence=min(pending.confidence, current.confidence, 0.85),
                )
                line_wrap_repairs += 1
                continue

            if pending:
                paragraphs.append(pending)
            pending = current

    if pending:
        paragraphs.append(pending)

    numbered = [
        Paragraph(
            element_id=f"p{index + 1:04d}",
            text=paragraph.text,
            source_refs=paragraph.source_refs,
            confidence=paragraph.confidence,
            warnings=paragraph.warnings,
        )
        for index, paragraph in enumerate(paragraphs)
    ]

    return ParagraphReconstructionResult(
        paragraphs=numbered,
        hyphenation_repairs=hyphenation_repairs,
        line_wrap_repairs=line_wrap_repairs,
        warnings=[],
    )


def paragraphs_to_elements(paragraphs: list[Paragraph]) -> list[DocumentElement]:
    return [
        DocumentElement(
            element_id=paragraph.element_id,
            element_type="paragraph",
            text=paragraph.text,
            source_refs=paragraph.source_refs,
            confidence=paragraph.confidence,
            warnings=paragraph.warnings,
        )
        for paragraph in paragraphs
    ]


def _merge_block_lines(text: str, dehyphenate: bool) -> tuple[str, int, int]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", 0, 0

    output = lines[0]
    hyphenation_repairs = 0
    line_wrap_repairs = 0

    for next_line in lines[1:]:
        if dehyphenate and _can_dehyphenate(output, next_line):
            output = output[:-1] + next_line
            hyphenation_repairs += 1
        else:
            output = f"{output} {next_line}"
        line_wrap_repairs += 1

    return re.sub(r"\s+", " ", output).strip(), hyphenation_repairs, line_wrap_repairs


def _split_block_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [part for part in re.split(r"\n\s*\n+", normalized) if part.strip()]


def _can_dehyphenate(current: str, next_line: str) -> bool:
    if not current.endswith("-") or not next_line:
        return False
    first = next_line[0]
    previous = current[-2] if len(current) >= 2 else ""
    return previous.isalpha() and first.isalpha() and first.islower()


def _can_merge_blocks(previous: Paragraph, block: RawTextBlock) -> bool:
    last_ref = previous.source_refs[-1]
    if last_ref.page_index != block.page_index:
        return False
    if abs(last_ref.bbox.x0 - block.bbox.x0) > 8:
        return False
    vertical_gap = block.bbox.y0 - last_ref.bbox.y1
    if vertical_gap < 0 or vertical_gap > 18:
        return False
    if _SENTENCE_END_RE.search(previous.text):
        return False
    return bool(block.raw_text.strip()) and block.raw_text.strip()[0].islower()
