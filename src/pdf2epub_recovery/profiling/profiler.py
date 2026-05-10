"""PDF profiling."""

from __future__ import annotations

import re
from pathlib import Path

from pdf2epub_recovery.model import LayoutEstimate, PageProfile, PdfProfile, QualityWarning

_PDF_HEADER_RE = re.compile(rb"^%PDF-(\d\.\d)")
_PAGE_OBJECT_RE = re.compile(rb"/Type\s*/Page\b")


def profile_pdf(path: Path, max_pages: int | None = None) -> PdfProfile:
    """Return a conservative PDF profile using PyMuPDF when possible."""

    if not path.exists():
        return PdfProfile(
            input_path=str(path),
            is_pdf=False,
            pdf_version=None,
            page_count=None,
            approximate_page_count=None,
            file_size_bytes=0,
            warnings=[
                QualityWarning(
                    code="input_missing",
                    severity="error",
                    message="Input file does not exist.",
                )
            ],
        )

    file_size = path.stat().st_size
    header = _read_header(path)
    header_match = _PDF_HEADER_RE.match(header)
    if header_match is None:
        return PdfProfile(
            input_path=str(path),
            is_pdf=False,
            pdf_version=None,
            page_count=None,
            approximate_page_count=None,
            file_size_bytes=file_size,
            warnings=[
                QualityWarning(
                    code="not_a_pdf",
                    severity="error",
                    message="Input does not start with a valid PDF header.",
                )
            ],
        )

    try:
        return _profile_with_pymupdf(
            path, file_size, header_match.group(1).decode("ascii"), max_pages
        )
    except Exception as exc:
        return _fallback_profile(path, file_size, header_match.group(1).decode("ascii"), exc)


def _profile_with_pymupdf(
    path: Path, file_size: int, pdf_version: str, max_pages: int | None
) -> PdfProfile:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency is installed in tests
        raise RuntimeError("PyMuPDF is not installed.") from exc

    warnings: list[QualityWarning] = []
    page_profiles: list[PageProfile] = []
    page_sizes: list[tuple[float, float]] = []
    native_text_pages = 0
    image_or_no_text_pages = 0
    total_chars = 0

    with fitz.open(path) as document:
        page_count = document.page_count
        limit = min(page_count, max_pages) if max_pages else page_count

        for page_index in range(limit):
            page = document.load_page(page_index)
            rect = page.rect
            blocks = [block for block in page.get_text("blocks") if _is_text_block(block)]
            image_count = len(page.get_images(full=True))
            text = page.get_text("text") or ""
            char_count = len(text.strip())
            layout = _estimate_page_layout(blocks, float(rect.width))

            if char_count > 0:
                native_text_pages += 1
            else:
                image_or_no_text_pages += 1

            total_chars += char_count
            page_sizes.append((float(rect.width), float(rect.height)))

            page_warnings: list[QualityWarning] = []
            if char_count == 0:
                page_warnings.append(
                    QualityWarning(
                        code="page_has_no_native_text",
                        message="Page has no extracted native text; OCR is not implemented.",
                        page_index=page_index,
                    )
                )

            page_profiles.append(
                PageProfile(
                    page_index=page_index,
                    width=float(rect.width),
                    height=float(rect.height),
                    text_block_count=len(blocks),
                    extracted_char_count=char_count,
                    image_count=image_count,
                    likely_layout=layout,
                    warnings=page_warnings,
                )
            )

        if max_pages and max_pages < page_count:
            warnings.append(
                QualityWarning(
                    code="max_pages_applied",
                    severity="info",
                    message=f"Profile limited to first {max_pages} pages.",
                )
            )

        likely_layout = _combine_layouts([page.likely_layout for page in page_profiles])
        if likely_layout == "possible_multi_column":
            warnings.append(
                QualityWarning(
                    code="possible_multi_column",
                    message="Some pages look like possible multi-column layouts.",
                )
            )

        if image_or_no_text_pages:
            warnings.append(
                QualityWarning(
                    code="image_or_no_text_pages_present",
                    message=(
                        "One or more pages have no native text. OCR is not implemented in MVP 1."
                    ),
                )
            )

        metadata = {key: value for key, value in (document.metadata or {}).items() if value}

    return PdfProfile(
        input_path=str(path),
        is_pdf=True,
        pdf_version=pdf_version,
        page_count=page_count,
        approximate_page_count=page_count,
        file_size_bytes=file_size,
        page_sizes=page_sizes,
        native_text_page_count=native_text_pages,
        image_only_or_no_text_page_count=image_or_no_text_pages,
        total_extracted_char_count=total_chars,
        likely_layout=likely_layout,
        warnings=warnings,
        page_profiles=page_profiles,
        metadata=metadata,
    )


def _fallback_profile(path: Path, file_size: int, pdf_version: str, exc: Exception) -> PdfProfile:
    data = path.read_bytes()
    approximate_page_count = len(_PAGE_OBJECT_RE.findall(data))
    warnings = [
        QualityWarning(
            code="pdf_engine_unavailable",
            severity="warning",
            message=f"Real PDF profiling failed; using approximate fallback. Reason: {exc}",
        ),
        QualityWarning(
            code="approximate_page_count",
            severity="info",
            message=(
                "Page count is approximate because the real PDF engine could not open the file."
            ),
        ),
    ]
    if approximate_page_count == 0:
        warnings.append(
            QualityWarning(
                code="no_page_objects_found",
                severity="warning",
                message="No page objects were found by the fallback regex profiler.",
            )
        )

    return PdfProfile(
        input_path=str(path),
        is_pdf=True,
        pdf_version=pdf_version,
        page_count=None,
        approximate_page_count=approximate_page_count,
        file_size_bytes=file_size,
        warnings=warnings,
    )


def _read_header(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read(16)


def _is_text_block(block: tuple[object, ...]) -> bool:
    if len(block) < 7:
        return True
    return int(block[6]) == 0 and bool(str(block[4]).strip())


def _estimate_page_layout(blocks: list[tuple[object, ...]], page_width: float) -> LayoutEstimate:
    text_blocks = [block for block in blocks if _is_text_block(block)]
    if len(text_blocks) < 4:
        return "one_column" if text_blocks else "unknown"

    centers = [((float(block[0]) + float(block[2])) / 2.0) / page_width for block in text_blocks]
    left = sum(1 for center in centers if center < 0.45)
    right = sum(1 for center in centers if center > 0.55)
    middle = sum(1 for center in centers if 0.45 <= center <= 0.55)

    if left >= 2 and right >= 2 and middle == 0:
        return "possible_multi_column"
    return "one_column"


def _combine_layouts(layouts: list[LayoutEstimate]) -> LayoutEstimate:
    if not layouts:
        return "unknown"
    if "possible_multi_column" in layouts:
        return "possible_multi_column"
    if all(layout == "one_column" for layout in layouts):
        return "one_column"
    return "unknown"
