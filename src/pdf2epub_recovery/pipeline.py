"""MVP conversion pipeline."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from pdf2epub_recovery.cleaning.page_artifacts import remove_page_artifacts
from pdf2epub_recovery.extraction.pymupdf_extractor import PyMuPDFExtractor
from pdf2epub_recovery.model import (
    DocumentElement,
    DocumentImage,
    DocumentIR,
    DocumentTocEntry,
    ExtractedDocument,
    ExtractedImage,
    PdfProfile,
    QualityReport,
    QualityWarning,
    RawTextBlock,
    RemovedArtifact,
    ReportActions,
)
from pdf2epub_recovery.profiling.profiler import profile_pdf
from pdf2epub_recovery.reading_order.resolver import resolve_reading_order
from pdf2epub_recovery.rendering.epub import render_epub
from pdf2epub_recovery.structure.paragraphs import paragraphs_to_elements, reconstruct_paragraphs
from pdf2epub_recovery.structure.tables import detect_table_like_blocks
from pdf2epub_recovery.structure.toc import detect_toc_blocks


@dataclass(frozen=True)
class ConversionResult:
    profile: PdfProfile
    extracted: ExtractedDocument
    ir: DocumentIR
    report: QualityReport
    ordered_blocks: list[RawTextBlock]
    keep_artifacts: bool = False
    decorative_image_ids: set[str] | None = None


ProgressCallback = Callable[[int, str], None]


def convert_pdf_to_epub(
    input_path: Path,
    output_path: Path,
    *,
    keep_artifacts: bool = False,
    dehyphenate: bool = True,
    max_pages: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ConversionResult:
    """Run the first real vertical slice and write the EPUB."""

    _progress(progress_callback, 5, "Profiling PDF.")
    profile = profile_pdf(input_path, max_pages=max_pages)
    if not profile.is_pdf:
        report = _build_error_report(input_path, output_path, profile)
        raise ConversionError("Input is not a readable PDF.", report)

    _progress(progress_callback, 20, "Extracting native text blocks and images.")
    extractor = PyMuPDFExtractor()
    extracted = extractor.extract(input_path, max_pages=max_pages)
    raw_blocks = extracted.raw_blocks

    _progress(progress_callback, 40, "Removing safe page artifacts.")
    cleanup = remove_page_artifacts(raw_blocks, keep_artifacts=keep_artifacts)
    _progress(progress_callback, 55, "Resolving reading order.")
    ordered = resolve_reading_order(
        cleanup.kept_blocks,
        profile.likely_layout,
        page_layouts={page.page_index: page.likely_layout for page in profile.page_profiles},
    )
    toc_detection = detect_toc_blocks(ordered.blocks)
    table_detection = detect_table_like_blocks(toc_detection.text_blocks)
    _progress(progress_callback, 70, "Reconstructing paragraphs.")
    reconstructed = reconstruct_paragraphs(table_detection.text_blocks, dehyphenate=dehyphenate)
    decorative_image_ids = _decorative_image_ids(extracted)
    image_elements, unsupported_warnings = _image_elements_and_warnings(
        extracted,
        decorative_image_ids=decorative_image_ids,
    )

    metadata = {
        "title": extracted.metadata.get("title") or input_path.stem,
        "author": extracted.metadata.get("author"),
        "language": extracted.metadata.get("language") or "en",
    }
    elements = _merge_adjacent_callouts(
        _sort_elements_by_source(
            [
                *paragraphs_to_elements(reconstructed.paragraphs),
                *toc_detection.toc_elements,
                *table_detection.table_elements,
                *image_elements,
            ]
        )
    )
    elements, toc_target_warnings = _resolve_toc_targets(elements, cleanup.removed_artifacts)
    all_warnings = [
        *profile.warnings,
        *extracted.warnings,
        *ordered.warnings,
        *toc_detection.warnings,
        *toc_target_warnings,
        *table_detection.warnings,
        *reconstructed.warnings,
        *unsupported_warnings,
    ]
    ir = DocumentIR(
        metadata=metadata,
        elements=elements,
        removed_artifacts=cleanup.removed_artifacts,
        warnings=all_warnings,
    )

    _progress(progress_callback, 85, "Writing EPUB.")
    render_epub(ir, output_path)
    _progress(progress_callback, 95, "Writing quality report data.")
    image_count = _detected_image_count(extracted)
    semantic_table_count = _semantic_table_count(table_detection.table_elements)
    table_fallback_count = _table_fallback_count(table_detection.table_elements)
    report = build_quality_report(
        input_path=input_path,
        output_path=output_path,
        profile=profile,
        total_raw_blocks=len(raw_blocks),
        total_paragraphs=len(reconstructed.paragraphs),
        removed_artifacts=cleanup.removed_artifacts,
        hyphenation_repairs=reconstructed.hyphenation_repairs,
        line_wrap_repairs=reconstructed.line_wrap_repairs,
        images_detected=image_count,
        images_preserved=len(image_elements),
        images_not_preserved=image_count - len(image_elements) - len(decorative_image_ids),
        decorative_images_removed=len(decorative_image_ids),
        table_like_blocks_detected=len(table_detection.table_blocks),
        tables_rendered_semantically=semantic_table_count,
        table_fallbacks_rendered=table_fallback_count,
        reading_order_warnings=ordered.warnings,
        unsupported_feature_warnings=unsupported_warnings,
        warnings=all_warnings,
    )
    _progress(progress_callback, 100, "Done.")
    return ConversionResult(
        profile=profile,
        extracted=extracted,
        ir=ir,
        report=report,
        ordered_blocks=ordered.blocks,
        keep_artifacts=keep_artifacts,
        decorative_image_ids=decorative_image_ids,
    )


class ConversionError(RuntimeError):
    """Conversion failed with a report that can still be written."""

    def __init__(self, message: str, report: QualityReport) -> None:
        super().__init__(message)
        self.report = report


def build_quality_report(
    *,
    input_path: Path,
    output_path: Path | None,
    profile: PdfProfile,
    total_raw_blocks: int,
    total_paragraphs: int,
    removed_artifacts: list[RemovedArtifact],
    hyphenation_repairs: int,
    line_wrap_repairs: int,
    images_detected: int = 0,
    images_preserved: int = 0,
    images_not_preserved: int = 0,
    decorative_images_removed: int = 0,
    table_like_blocks_detected: int = 0,
    tables_rendered_semantically: int = 0,
    table_fallbacks_rendered: int = 0,
    reading_order_warnings: list[QualityWarning],
    unsupported_feature_warnings: list[QualityWarning],
    warnings: list[QualityWarning],
) -> QualityReport:
    actions = ReportActions(
        page_numbers_removed=sum(
            1 for artifact in removed_artifacts if artifact.artifact_type == "page_number"
        ),
        headers_removed=sum(
            1 for artifact in removed_artifacts if artifact.artifact_type == "header"
        ),
        footers_removed=sum(
            1 for artifact in removed_artifacts if artifact.artifact_type == "footer"
        ),
        hyphenations_repaired=hyphenation_repairs,
        line_wraps_repaired=line_wrap_repairs,
        images_detected=images_detected,
        images_preserved=images_preserved,
        images_not_preserved=images_not_preserved,
        decorative_images_removed=decorative_images_removed,
        table_like_blocks_detected=table_like_blocks_detected,
        tables_rendered_semantically=tables_rendered_semantically,
        table_fallbacks_rendered=table_fallbacks_rendered,
    )
    status = _status_from_warnings(warnings)
    return QualityReport(
        input_path=str(input_path),
        output_path=str(output_path) if output_path else None,
        status=status,
        quality_score=_quality_score(profile, reading_order_warnings, unsupported_feature_warnings),
        page_count=profile.page_count or profile.approximate_page_count or 0,
        native_text_page_count=profile.native_text_page_count,
        image_only_or_no_text_page_count=profile.image_only_or_no_text_page_count,
        total_raw_blocks=total_raw_blocks,
        total_paragraphs=total_paragraphs,
        actions=actions,
        removed_artifacts=removed_artifacts,
        reading_order_warnings=reading_order_warnings,
        unsupported_feature_warnings=unsupported_feature_warnings,
        warnings=warnings,
        dependency_notes=[
            "PyMuPDF used for native text extraction.",
            "EPUB written with the project stdlib-based minimal EPUB writer.",
            "EPUBCheck is optional and not run during conversion.",
        ],
        validation={"epubcheck": "not_run"},
    )


def _image_elements_and_warnings(
    extracted: ExtractedDocument,
    decorative_image_ids: set[str] | None = None,
) -> tuple[list[DocumentElement], list[QualityWarning]]:
    image_elements: list[DocumentElement] = []
    warnings: list[QualityWarning] = []
    decorative_image_ids = decorative_image_ids or set()

    for image in (image for page in extracted.pages for image in page.images):
        if image.image_id in decorative_image_ids:
            continue
        if _can_preserve_image(image):
            alt_text = (
                _caption_text_for_image(image, extracted)
                or f"Image from page {image.page_index + 1}"
            )
            document_image = DocumentImage(
                image_id=image.image_id,
                file_name=f"images/{image.image_id}.{image.extension}",
                media_type=str(image.media_type),
                data=image.data or b"",
                alt_text=alt_text,
                source_refs=[image.source_ref()],
                pixel_width=image.pixel_width,
                pixel_height=image.pixel_height,
                confidence=image.confidence,
                warnings=image.warnings,
            )
            image_elements.append(
                DocumentElement(
                    element_id=image.image_id,
                    element_type="image",
                    text=document_image.alt_text,
                    source_refs=document_image.source_refs,
                    confidence=document_image.confidence,
                    warnings=document_image.warnings,
                    image=document_image,
                )
            )
            continue

        warning = _image_not_preserved_warning(image)
        warnings.append(warning)

    return image_elements, warnings


def _detected_image_count(extracted: ExtractedDocument) -> int:
    return sum(page.image_count or len(page.images) for page in extracted.pages)


def _decorative_image_ids(extracted: ExtractedDocument) -> set[str]:
    groups: dict[tuple[object, ...], list[ExtractedImage]] = {}
    for image in (image for page in extracted.pages for image in page.images):
        if not _is_small_margin_image(image):
            continue
        groups.setdefault(_decorative_image_key(image), []).append(image)

    decorative: set[str] = set()
    for images in groups.values():
        if len({image.page_index for image in images}) >= 3:
            decorative.update(image.image_id for image in images)
    return decorative


def _is_small_margin_image(image: ExtractedImage) -> bool:
    if image.bbox.width > max(48.0, image.page_width * 0.09):
        return False
    if image.bbox.height > max(48.0, image.page_height * 0.09):
        return False
    if image.pixel_width and image.pixel_width > 160:
        return False
    if image.pixel_height and image.pixel_height > 160:
        return False
    return _image_margin_zone(image) is not None


def _decorative_image_key(image: ExtractedImage) -> tuple[object, ...]:
    return (
        image.xref if image.xref is not None else image.media_type,
        image.pixel_width,
        image.pixel_height,
        _image_margin_zone(image),
    )


def _image_margin_zone(image: ExtractedImage) -> str | None:
    if image.bbox.y1 <= image.page_height * 0.15:
        return "top"
    if image.bbox.y0 >= image.page_height * 0.85:
        return "bottom"
    if image.bbox.x1 <= image.page_width * 0.18:
        return "left"
    if image.bbox.x0 >= image.page_width * 0.82:
        return "right"
    return None


def _caption_text_for_image(image: ExtractedImage, extracted: ExtractedDocument) -> str | None:
    page = next((page for page in extracted.pages if page.page_index == image.page_index), None)
    if page is None:
        return None
    candidates = [
        block
        for block in page.text_blocks
        if _looks_like_caption(block.raw_text)
        and _caption_near_image(block, image)
    ]
    candidates.sort(key=lambda block: abs(block.bbox.y0 - image.bbox.y1))
    if not candidates:
        return None
    return " ".join(candidates[0].raw_text.split())


def _looks_like_caption(text: str) -> bool:
    return bool(re.match(r"^\s*(?:abb\.?|fig\.?|figure)\s+\d+", text.strip(), re.IGNORECASE))


def _caption_near_image(block: RawTextBlock, image: ExtractedImage) -> bool:
    vertical_gap = min(
        abs(block.bbox.y0 - image.bbox.y1),
        abs(image.bbox.y0 - block.bbox.y1),
    )
    if vertical_gap > 42:
        return False
    overlap = min(block.bbox.x1, image.bbox.x1) - max(block.bbox.x0, image.bbox.x0)
    return overlap >= min(block.bbox.width, image.bbox.width) * 0.25


def _semantic_table_count(elements: list[DocumentElement]) -> int:
    return sum(
        1
        for element in elements
        if element.element_type == "table" and element.table is not None
    )


def _table_fallback_count(elements: list[DocumentElement]) -> int:
    return sum(
        1
        for element in elements
        if element.element_type == "table" and element.table is None
    )


def _resolve_toc_targets(
    elements: list[DocumentElement],
    removed_artifacts: list[RemovedArtifact],
) -> tuple[list[DocumentElement], list[QualityWarning]]:
    toc_elements = [element for element in elements if element.element_type == "toc"]
    if not toc_elements:
        return elements, []

    page_by_label = _page_label_map(removed_artifacts)
    max_page_index = max(
        (
            ref.page_index
            for element in elements
            for ref in element.source_refs
        ),
        default=-1,
    )
    warnings: list[QualityWarning] = []
    updated_elements: list[DocumentElement] = []

    for element in elements:
        if element.element_type != "toc":
            updated_elements.append(element)
            continue

        resolved_entries: list[DocumentTocEntry] = []
        element_warnings = list(element.warnings)
        for entry in element.toc_entries:
            target_page = _target_page_for_toc_entry(
                entry,
                page_by_label=page_by_label,
                max_page_index=max_page_index,
            )
            target = (
                _first_toc_target_on_page(elements, target_page)
                if target_page is not None
                else None
            )
            if target is None:
                warning = QualityWarning(
                    code="toc_entry_unresolved",
                    severity="info",
                    message=(
                        "Table of contents entry was preserved without a link because "
                        "no safe EPUB target could be resolved."
                    ),
                    page_index=element.source_refs[0].page_index if element.source_refs else None,
                )
                warnings.append(warning)
                element_warnings.append(warning)
                resolved_entries.append(entry)
                continue
            resolved_entries.append(replace(entry, target_id=target.element_id))

        updated_elements.append(
            replace(element, toc_entries=resolved_entries, warnings=element_warnings)
        )

    return updated_elements, warnings


def _page_label_map(removed_artifacts: list[RemovedArtifact]) -> dict[int, int]:
    page_by_label: dict[int, int] = {}
    for artifact in removed_artifacts:
        if artifact.artifact_type != "page_number":
            continue
        page_label = _page_number_from_text(artifact.text)
        if page_label is not None:
            page_by_label.setdefault(page_label, artifact.source_ref.page_index)
    return page_by_label


def _target_page_for_toc_entry(
    entry: DocumentTocEntry,
    *,
    page_by_label: dict[int, int],
    max_page_index: int,
) -> int | None:
    if entry.page_label is None:
        return None
    page_label = _page_number_from_text(entry.page_label)
    if page_label is None:
        return None
    if page_label in page_by_label:
        return page_by_label[page_label]
    fallback = page_label - 1
    if 0 <= fallback <= max_page_index:
        return fallback
    return None


def _first_toc_target_on_page(
    elements: list[DocumentElement], page_index: int | None
) -> DocumentElement | None:
    if page_index is None:
        return None
    candidates = [
        element
        for element in elements
        if element.element_type in {"paragraph", "callout", "table"}
        and element.source_refs
        and element.source_refs[0].page_index == page_index
        and _is_toc_target_text(element.text)
    ]
    candidates.sort(key=_element_sort_key)
    return candidates[0] if candidates else None


def _is_toc_target_text(text: str) -> bool:
    stripped = " ".join(text.split()).strip()
    if not stripped or stripped.casefold() == "notizen":
        return False
    return _page_number_from_text(stripped) is None


def _page_number_from_text(text: str) -> int | None:
    match = re.match(
        r"^(?:(?:page|seite|p\.|s\.)\s*)?(\d{1,5})(?:\s*(?:of|von|/)\s*\d{1,5})?$",
        text.strip(),
        re.IGNORECASE,
    )
    if match is None:
        return None
    return int(match.group(1))


def _can_preserve_image(image: ExtractedImage) -> bool:
    return bool(image.data and image.extension and image.media_type)


def _image_not_preserved_warning(image: ExtractedImage) -> QualityWarning:
    detail = (
        image.warnings[0].message
        if image.warnings
        else "No extracted image bytes were available."
    )
    return QualityWarning(
        code="image_not_preserved",
        message=f"Image on page {image.page_index + 1} was not preserved. {detail}",
        page_index=image.page_index,
    )


def _sort_elements_by_source(elements: list[DocumentElement]) -> list[DocumentElement]:
    return sorted(elements, key=_element_sort_key)


def _merge_adjacent_callouts(elements: list[DocumentElement]) -> list[DocumentElement]:
    merged: list[DocumentElement] = []
    pending: DocumentElement | None = None

    for element in elements:
        if element.element_type != "callout":
            if pending is not None:
                merged.append(pending)
                pending = None
            merged.append(element)
            continue

        if pending is None:
            pending = element
            continue

        if _can_merge_callout_elements(pending, element):
            pending = DocumentElement(
                element_id=pending.element_id,
                element_type="callout",
                text=f"{pending.text}\n\n{element.text}",
                source_refs=[*pending.source_refs, *element.source_refs],
                confidence=min(pending.confidence, element.confidence),
                warnings=[*pending.warnings, *element.warnings],
            )
            continue

        merged.append(pending)
        pending = element

    if pending is not None:
        merged.append(pending)
    return merged


def _can_merge_callout_elements(previous: DocumentElement, current: DocumentElement) -> bool:
    if not previous.source_refs or not current.source_refs:
        return False
    previous_ref = previous.source_refs[-1]
    current_ref = current.source_refs[0]
    if previous_ref.page_index != current_ref.page_index:
        return False
    vertical_gap = current_ref.bbox.y0 - previous_ref.bbox.y1
    if vertical_gap < -2 or vertical_gap > 28:
        return False
    return abs(previous_ref.bbox.x0 - current_ref.bbox.x0) <= 16


def _element_sort_key(element: DocumentElement) -> tuple[int, float, float, str]:
    if not element.source_refs:
        return (10**9, 0.0, 0.0, element.element_id)
    ref = element.source_refs[0]
    return (
        ref.page_index,
        round(ref.bbox.y0, 1),
        round(ref.bbox.x0, 1),
        element.element_id,
    )


def _status_from_warnings(warnings: list[QualityWarning]) -> str:
    if any(warning.severity == "error" for warning in warnings):
        return "error"
    if warnings:
        return "warning"
    return "ok"


def _quality_score(
    profile: PdfProfile,
    reading_order_warnings: list[QualityWarning],
    unsupported_feature_warnings: list[QualityWarning],
) -> int:
    score = 100
    page_count = profile.page_count or profile.approximate_page_count or 0
    if page_count:
        no_text_ratio = profile.image_only_or_no_text_page_count / page_count
        score -= round(no_text_ratio * 25)
    if profile.likely_layout == "possible_multi_column":
        score -= 20
    score -= min(20, len(reading_order_warnings) * 5)
    score -= min(15, len(unsupported_feature_warnings) * 5)
    if profile.total_extracted_char_count == 0:
        score -= 30
    return max(0, min(100, score))


def _build_error_report(
    input_path: Path, output_path: Path | None, profile: PdfProfile
) -> QualityReport:
    return QualityReport(
        input_path=str(input_path),
        output_path=str(output_path) if output_path else None,
        status="error",
        quality_score=0,
        page_count=0,
        native_text_page_count=0,
        image_only_or_no_text_page_count=0,
        total_raw_blocks=0,
        total_paragraphs=0,
        actions=ReportActions(),
        warnings=profile.warnings,
        dependency_notes=[
            "Conversion stopped before extraction.",
            "PyMuPDF is required for successful MVP PDF extraction.",
        ],
        validation={"epubcheck": "not_run"},
    )


def _progress(callback: ProgressCallback | None, percent: int, message: str) -> None:
    if callback:
        callback(percent, message)
