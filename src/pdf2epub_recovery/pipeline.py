"""MVP conversion pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pdf2epub_recovery.cleaning.page_artifacts import remove_page_artifacts
from pdf2epub_recovery.extraction.pymupdf_extractor import PyMuPDFExtractor
from pdf2epub_recovery.model import (
    DocumentElement,
    DocumentImage,
    DocumentIR,
    ExtractedDocument,
    ExtractedImage,
    PdfProfile,
    QualityReport,
    QualityWarning,
    RemovedArtifact,
    ReportActions,
)
from pdf2epub_recovery.profiling.profiler import profile_pdf
from pdf2epub_recovery.reading_order.resolver import resolve_reading_order
from pdf2epub_recovery.rendering.epub import render_epub
from pdf2epub_recovery.structure.paragraphs import paragraphs_to_elements, reconstruct_paragraphs
from pdf2epub_recovery.structure.tables import detect_table_like_blocks


@dataclass(frozen=True)
class ConversionResult:
    profile: PdfProfile
    ir: DocumentIR
    report: QualityReport


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
    ordered = resolve_reading_order(cleanup.kept_blocks, profile.likely_layout)
    table_detection = detect_table_like_blocks(ordered.blocks)
    _progress(progress_callback, 70, "Reconstructing paragraphs.")
    reconstructed = reconstruct_paragraphs(table_detection.text_blocks, dehyphenate=dehyphenate)
    image_elements, unsupported_warnings = _image_elements_and_warnings(extracted)

    metadata = {
        "title": extracted.metadata.get("title") or input_path.stem,
        "author": extracted.metadata.get("author"),
        "language": extracted.metadata.get("language") or "en",
    }
    all_warnings = [
        *profile.warnings,
        *extracted.warnings,
        *ordered.warnings,
        *table_detection.warnings,
        *reconstructed.warnings,
        *unsupported_warnings,
    ]
    elements = _sort_elements_by_source(
        [
            *paragraphs_to_elements(reconstructed.paragraphs),
            *table_detection.table_elements,
            *image_elements,
        ]
    )
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
        images_not_preserved=image_count - len(image_elements),
        table_like_blocks_detected=len(table_detection.table_blocks),
        table_fallbacks_rendered=len(table_detection.table_elements),
        reading_order_warnings=ordered.warnings,
        unsupported_feature_warnings=unsupported_warnings,
        warnings=all_warnings,
    )
    _progress(progress_callback, 100, "Done.")
    return ConversionResult(profile=profile, ir=ir, report=report)


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
    table_like_blocks_detected: int = 0,
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
        table_like_blocks_detected=table_like_blocks_detected,
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
            "EbookLib used for basic EPUB writing.",
            "EPUBCheck is optional and not run during conversion.",
        ],
        validation={"epubcheck": "not_run"},
    )


def _image_elements_and_warnings(
    extracted: ExtractedDocument,
) -> tuple[list[DocumentElement], list[QualityWarning]]:
    image_elements: list[DocumentElement] = []
    warnings: list[QualityWarning] = []

    for image in (image for page in extracted.pages for image in page.images):
        if _can_preserve_image(image):
            document_image = DocumentImage(
                image_id=image.image_id,
                file_name=f"images/{image.image_id}.{image.extension}",
                media_type=str(image.media_type),
                data=image.data or b"",
                alt_text=f"Image from page {image.page_index + 1}",
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
            "PyMuPDF and EbookLib are required for successful MVP conversion.",
        ],
        validation={"epubcheck": "not_run"},
    )


def _progress(callback: ProgressCallback | None, percent: int, message: str) -> None:
    if callback:
        callback(percent, message)
