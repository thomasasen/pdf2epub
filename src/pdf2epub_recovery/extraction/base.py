"""Extraction interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pdf2epub_recovery.model import ExtractedDocument


class PdfExtractor(Protocol):
    """Protocol for PDF extraction adapters."""

    source_engine: str

    def extract(self, path: Path, max_pages: int | None = None) -> ExtractedDocument:
        """Extract raw document facts from a PDF."""
