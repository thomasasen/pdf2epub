"""MVP conversion pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pdf2epub_recovery.cleaning.page_artifacts import remove_page_artifacts
from pdf2epub_recovery.extraction.pymupdf_extractor import PyMuPDFExtractor
from pdf2epub_recovery.model import (
    DocumentIR,
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

    _progress(progress_callback, 20, "Extracting native text blocks.")
    extractor = PyMuPDFExtractor()
    extracted = extractor.extract(input_path, max_pages=max_pages)
    raw_blocks = extracted.raw_blocks

    _progress(progress_callback, 40, "Removing safe page artifacts.")
    cleanup = remove_page_artifacts(raw_blocks, keep_artifacts=keep_artifacts)
    _progress(progress_callback, 55, "Resolving reading order.")
    ordered = resolve_reading_order(cleanup.kept_blocks, profile.likely_layout)
    _progress(progress_callback, 70, "Reconstructing paragraphs.")
    reconstructed = reconstruct_paragraphs(ordered.blocks, dehyphenate=dehyphenate)
    unsupported_warnings = _unsupported_warnings(extracted)

    metadata = {
        "title": extracted.metadata.get("title") or input_path.stem,
        "author": extracted.metadata.get("author"),
        "language": extracted.metadata.get("language") or "en",
    }
    all_warnings = [
        *profile.warnings,
        *extracted.warnings,
        *ordered.warnings,
        *reconstructed.warnings,
        *unsupported_warnings,
    ]
    ir = DocumentIR(
        metadata=metadata,
        elements=paragraphs_to_elements(reconstructed.paragraphs),
        removed_artifacts=cleanup.removed_artifacts,
        warnings=all_warnings,
    )

    _progress(progress_callback, 85, "Writing EPUB.")
    render_epub(ir, output_path)
    _progress(progress_callback, 95, "Writing quality report data.")
    report = build_quality_report(
        input_path=input_path,
        output_path=output_path,
        profile=profile,
        total_raw_blocks=len(raw_blocks),
        total_paragraphs=len(reconstructed.paragraphs),
        removed_artifacts=cleanup.removed_artifacts,
        hyphenation_repairs=reconstructed.hyphenation_repairs,
        line_wrap_repairs=reconstructed.line_wrap_repairs,
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


def _unsupported_warnings(extracted) -> list[QualityWarning]:
    image_pages = [page.page_index for page in extracted.pages if page.image_count > 0]
    warnings: list[QualityWarning] = []
    for page_index in image_pages:
        warnings.append(
            QualityWarning(
                code="images_not_rendered_in_mvp",
                message="Images were detected but image preservation is not implemented in MVP 1.",
                page_index=page_index,
            )
        )
    return warnings


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
