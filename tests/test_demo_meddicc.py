import zipfile
from pathlib import Path

import pytest

from pdf2epub_recovery.pipeline import convert_pdf_to_epub

DEMO_MEDDICC_PDF = (
    Path(__file__).resolve().parents[1]
    / "demo"
    / "MEDDICC_Einfuehrung_und_Praxisleitfaden_erweitert.pdf"
)


@pytest.mark.skipif(
    not DEMO_MEDDICC_PDF.exists(),
    reason="MEDDICC demo PDF is not available in this checkout.",
)
def test_meddicc_demo_pdf_converts_cleanly(tmp_path: Path) -> None:
    epub = tmp_path / "meddicc.epub"

    result = convert_pdf_to_epub(DEMO_MEDDICC_PDF, epub)

    assert epub.exists()
    assert result.report.status == "warning"
    assert result.report.quality_score == 100
    assert result.report.page_count == 28
    assert result.report.native_text_page_count == 28
    assert result.report.image_only_or_no_text_page_count == 0
    assert result.report.actions.headers_removed == 27
    assert result.report.actions.page_numbers_removed == 27
    assert result.report.actions.line_wraps_repaired >= 200
    assert result.report.actions.table_like_blocks_detected >= 10
    assert result.report.actions.table_fallbacks_rendered >= 10
    assert any(warning.code == "table_fallback_used" for warning in result.report.warnings)

    with zipfile.ZipFile(epub) as archive:
        xhtml = archive.read("EPUB/text/text.xhtml").decode("utf-8")

    assert "MEDDICC kompakt" in xhtml
    assert "Metrics" in xhtml
    assert "Economic Buyer" in xhtml
    assert "Decision Criteria" in xhtml
    assert "Champion" in xhtml
    assert '<figure class="table-fallback" id="table-' in xhtml
    assert '<aside class="callout" id="' in xhtml
    assert '<p class="callout-title">Win Strategy</p>' in xhtml
    assert "<th>Feld</th><th>Inhalt</th>" in xhtml
    assert "<th>Element</th><th>Leitfrage</th><th>Status</th>" in xhtml
    assert "MEDDICC kompakt - Einfuehrung und Praxisleitfaden" not in xhtml
    assert "MEDDICC kompakt - Praxis-Erg" not in xhtml
