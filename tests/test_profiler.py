from __future__ import annotations

from pathlib import Path

from pdf2epub_recovery.profiling.profiler import profile_pdf
from tests.helpers import write_text_pdf


def test_missing_file_returns_error_profile(tmp_path: Path) -> None:
    profile = profile_pdf(tmp_path / "missing.pdf")

    assert profile.is_pdf is False
    assert profile.file_size_bytes == 0
    assert profile.warnings[0].code == "input_missing"


def test_real_pdf_profile_counts_native_text(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    write_text_pdf(pdf, ["Native text page one.", "Native text page two."])

    profile = profile_pdf(pdf)

    assert profile.is_pdf is True
    assert profile.pdf_version is not None
    assert profile.page_count == 2
    assert profile.approximate_page_count == 2
    assert profile.native_text_page_count == 2
    assert profile.image_only_or_no_text_page_count == 0
    assert len(profile.page_sizes) == 2


def test_possible_multi_column_profile_warns(tmp_path: Path) -> None:
    pdf = tmp_path / "columns.pdf"
    write_text_pdf(pdf, ["Left column text " * 8], two_columns=True)

    profile = profile_pdf(pdf)

    assert profile.likely_layout == "possible_multi_column"
    assert any(warning.code == "possible_multi_column" for warning in profile.warnings)
