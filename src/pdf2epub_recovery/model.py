"""Core serializable data models for the recovery pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal

Severity = Literal["info", "warning", "error"]
LayoutEstimate = Literal["one_column", "possible_multi_column", "unknown"]
ReportStatus = Literal["ok", "warning", "error"]


def json_ready(value: Any) -> Any:
    """Return a JSON-compatible representation of dataclasses and paths."""

    if is_dataclass(value):
        return {key: json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class QualityWarning:
    """A user-visible warning that should not be hidden."""

    code: str
    message: str
    severity: Severity = "warning"
    page_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return json_ready(self)


@dataclass(frozen=True)
class BBox:
    """PDF-space bounding box."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    def to_list(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]


@dataclass(frozen=True)
class SourceRef:
    """Trace back to a page/block and geometry where possible."""

    page_index: int
    block_id: str
    bbox: BBox
    engine: str


@dataclass(frozen=True)
class RawTextBlock:
    """Raw extracted PDF text block with provenance."""

    block_id: str
    page_index: int
    page_width: float
    page_height: float
    raw_text: str
    bbox: BBox
    source_engine: str
    confidence: float = 1.0
    warnings: list[QualityWarning] = field(default_factory=list)

    def source_ref(self) -> SourceRef:
        return SourceRef(
            page_index=self.page_index,
            block_id=self.block_id,
            bbox=self.bbox,
            engine=self.source_engine,
        )


@dataclass(frozen=True)
class ExtractedPage:
    """A page worth of raw extraction facts."""

    page_index: int
    width: float
    height: float
    text_blocks: list[RawTextBlock] = field(default_factory=list)
    image_count: int = 0
    warnings: list[QualityWarning] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedDocument:
    """Raw extraction output before cleaning and structure recovery."""

    input_path: str
    source_engine: str
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[ExtractedPage] = field(default_factory=list)
    warnings: list[QualityWarning] = field(default_factory=list)

    @property
    def raw_blocks(self) -> list[RawTextBlock]:
        return [block for page in self.pages for block in page.text_blocks]

    def to_dict(self) -> dict[str, Any]:
        return json_ready(self)


@dataclass(frozen=True)
class PageProfile:
    """Profile details for one PDF page."""

    page_index: int
    width: float
    height: float
    text_block_count: int
    extracted_char_count: int
    image_count: int
    likely_layout: LayoutEstimate
    warnings: list[QualityWarning] = field(default_factory=list)


@dataclass(frozen=True)
class PdfProfile:
    """Conservative PDF profile.

    Engine-derived values are used when available. Fallback values stay labelled
    as approximate to avoid presenting guesses as facts.
    """

    input_path: str
    is_pdf: bool
    pdf_version: str | None
    file_size_bytes: int
    page_count: int | None = None
    page_sizes: list[tuple[float, float]] = field(default_factory=list)
    native_text_page_count: int = 0
    image_only_or_no_text_page_count: int = 0
    total_extracted_char_count: int = 0
    likely_layout: LayoutEstimate = "unknown"
    warnings: list[QualityWarning] = field(default_factory=list)
    approximate_page_count: int | None = None
    page_profiles: list[PageProfile] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return json_ready(self)


@dataclass(frozen=True)
class Paragraph:
    """Recovered paragraph with source traceability."""

    element_id: str
    text: str
    source_refs: list[SourceRef]
    confidence: float = 0.9
    warnings: list[QualityWarning] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentElement:
    """Generic document IR element."""

    element_id: str
    element_type: Literal["paragraph", "warning"]
    text: str
    source_refs: list[SourceRef] = field(default_factory=list)
    confidence: float = 0.9
    warnings: list[QualityWarning] = field(default_factory=list)


@dataclass(frozen=True)
class RemovedArtifact:
    """Text removed from the output with evidence and provenance."""

    artifact_id: str
    artifact_type: Literal["page_number", "header", "footer"]
    text: str
    source_ref: SourceRef
    reason: str
    confidence: float


@dataclass(frozen=True)
class DocumentIR:
    """Minimal IR consumed by the EPUB renderer."""

    metadata: dict[str, Any]
    elements: list[DocumentElement]
    removed_artifacts: list[RemovedArtifact] = field(default_factory=list)
    warnings: list[QualityWarning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return json_ready(self)


@dataclass(frozen=True)
class ReportActions:
    """Counts of lossy or repair actions taken by the pipeline."""

    page_numbers_removed: int = 0
    headers_removed: int = 0
    footers_removed: int = 0
    hyphenations_repaired: int = 0
    line_wraps_repaired: int = 0


@dataclass(frozen=True)
class QualityReport:
    """Conversion report written alongside EPUB output."""

    input_path: str
    output_path: str | None
    status: ReportStatus
    quality_score: int
    page_count: int
    native_text_page_count: int
    image_only_or_no_text_page_count: int
    total_raw_blocks: int
    total_paragraphs: int
    actions: ReportActions
    removed_artifacts: list[RemovedArtifact] = field(default_factory=list)
    reading_order_warnings: list[QualityWarning] = field(default_factory=list)
    unsupported_feature_warnings: list[QualityWarning] = field(default_factory=list)
    warnings: list[QualityWarning] = field(default_factory=list)
    dependency_notes: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return json_ready(self)


@dataclass(frozen=True)
class CommandResult:
    """Simple command result for CLI operations."""

    status: Literal["ok", "not_implemented", "error"]
    message: str
    output_path: Path | None = None
