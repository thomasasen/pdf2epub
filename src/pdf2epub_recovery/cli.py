"""Command-line interface for pdf2epub-recovery."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pdf2epub_recovery import __version__
from pdf2epub_recovery.debug import build_debug_payloads
from pdf2epub_recovery.extraction.pymupdf_extractor import PyMuPDFExtractor
from pdf2epub_recovery.model import QualityReport, QualityWarning, ReportActions
from pdf2epub_recovery.pipeline import ConversionError, convert_pdf_to_epub
from pdf2epub_recovery.profiling.profiler import profile_pdf
from pdf2epub_recovery.validation import validate_epub
from pdf2epub_recovery.web import run_web_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2epub-recovery",
        description="Recover readable EPUB structure from PDFs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    profile_parser = subparsers.add_parser("profile", help="Create a PDF profile JSON.")
    profile_parser.add_argument("input", type=Path, help="Input PDF file.")
    profile_parser.add_argument("--out", type=Path, required=True, help="Output JSON profile path.")
    profile_parser.add_argument(
        "--max-pages", type=int, help="Limit profiling to the first N pages."
    )

    extract_parser = subparsers.add_parser("extract", help="Extract raw PDF blocks as JSON.")
    extract_parser.add_argument("input", type=Path, help="Input PDF file.")
    extract_parser.add_argument("--out", type=Path, required=True, help="Output JSON path.")
    extract_parser.add_argument(
        "--max-pages", type=int, help="Limit extraction to the first N pages."
    )

    convert_parser = subparsers.add_parser("convert", help="Convert a native-text PDF to EPUB.")
    convert_parser.add_argument("input", type=Path, help="Input PDF file.")
    convert_parser.add_argument("--out", type=Path, required=True, help="Output EPUB path.")
    convert_parser.add_argument("--report", type=Path, help="Optional JSON quality report path.")
    convert_parser.add_argument("--debug-dir", type=Path, help="Optional directory for debug JSON.")
    convert_parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep detected page numbers/headers/footers in output.",
    )
    convert_parser.add_argument(
        "--no-dehyphenate",
        action="store_true",
        help="Disable conservative hyphenation repair.",
    )
    convert_parser.add_argument(
        "--max-pages", type=int, help="Limit conversion to the first N pages."
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate an EPUB with EPUBCheck if set up."
    )
    validate_parser.add_argument("input", type=Path, help="Input EPUB file.")

    web_parser = subparsers.add_parser("web", help="Start the local web interface.")
    web_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind. Defaults to localhost."
    )
    web_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    web_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically.",
    )

    return parser


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _handle_profile(input_path: Path, out_path: Path, max_pages: int | None) -> int:
    profile = profile_pdf(input_path, max_pages=max_pages)
    _write_json(out_path, profile.to_dict())
    print(f"Wrote profile: {out_path}")
    return 0 if profile.is_pdf else 1


def _handle_extract(input_path: Path, out_path: Path, max_pages: int | None) -> int:
    profile = profile_pdf(input_path, max_pages=max_pages)
    if not profile.is_pdf:
        _write_json(out_path, {"profile": profile.to_dict(), "pages": []})
        print(f"Cannot extract: {profile.warnings[0].message if profile.warnings else 'not a PDF'}")
        return 1

    try:
        extracted = PyMuPDFExtractor().extract(input_path, max_pages=max_pages)
    except RuntimeError as exc:
        _write_json(out_path, {"profile": profile.to_dict(), "error": str(exc)})
        print(f"Extraction failed: {exc}")
        return 1

    _write_json(out_path, {"profile": profile.to_dict(), "extraction": extracted.to_dict()})
    print(f"Wrote extraction JSON: {out_path}")
    return 0


def _handle_convert(args: argparse.Namespace) -> int:
    try:
        result = convert_pdf_to_epub(
            args.input,
            args.out,
            keep_artifacts=args.keep_artifacts,
            dehyphenate=not args.no_dehyphenate,
            max_pages=args.max_pages,
        )
    except ConversionError as exc:
        if args.report:
            _write_json(args.report, exc.report.to_dict())
            print(f"Wrote quality report: {args.report}")
        print(f"Conversion failed: {exc}")
        return 1
    except RuntimeError as exc:
        if args.report:
            report = _runtime_error_report(args.input, args.out, exc)
            _write_json(args.report, report.to_dict())
            print(f"Wrote quality report: {args.report}")
        print(f"Conversion failed: {exc}")
        return 1

    if args.report:
        _write_json(args.report, result.report.to_dict())
        print(f"Wrote quality report: {args.report}")

    if args.debug_dir:
        args.debug_dir.mkdir(parents=True, exist_ok=True)
        _write_json(args.debug_dir / "profile.json", result.profile.to_dict())
        _write_json(args.debug_dir / "document-ir.json", result.ir.to_dict())
        for file_name, payload in build_debug_payloads(result).items():
            _write_json(args.debug_dir / file_name, payload)
        print(f"Wrote debug JSON: {args.debug_dir}")

    print(f"Wrote EPUB: {args.out}")
    return 0 if result.report.status in {"ok", "warning"} else 1


def _handle_validate(input_path: Path) -> int:
    exit_code, output = validate_epub(input_path)
    print(output)
    return exit_code


def _runtime_error_report(input_path: Path, output_path: Path, exc: RuntimeError) -> QualityReport:
    profile = profile_pdf(input_path)
    warnings = [
        *profile.warnings,
        QualityWarning(
            code="conversion_failed",
            severity="error",
            message=str(exc),
        ),
    ]
    return QualityReport(
        input_path=str(input_path),
        output_path=str(output_path),
        status="error",
        quality_score=0,
        page_count=profile.page_count or profile.approximate_page_count or 0,
        native_text_page_count=profile.native_text_page_count,
        image_only_or_no_text_page_count=profile.image_only_or_no_text_page_count,
        total_raw_blocks=0,
        total_paragraphs=0,
        actions=ReportActions(),
        warnings=warnings,
        dependency_notes=["Conversion failed before EPUB output could be completed."],
        validation={"epubcheck": "not_run"},
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "profile":
        return _handle_profile(args.input, args.out, args.max_pages)

    if args.command == "extract":
        return _handle_extract(args.input, args.out, args.max_pages)

    if args.command == "convert":
        return _handle_convert(args)

    if args.command == "validate":
        return _handle_validate(args.input)

    if args.command == "web":
        run_web_server(args.host, args.port, open_browser=not args.no_browser)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
