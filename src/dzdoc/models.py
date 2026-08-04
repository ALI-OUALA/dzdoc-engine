"""Canonical versioned document representation."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"

Identifier = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]


class LanguageTag(StrEnum):
    ARABIC = "ar"
    FRENCH = "fr"
    ENGLISH = "en"
    LATIN = "latin"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ScriptTag(StrEnum):
    ARABIC = "arabic"
    LATIN = "latin"
    MIXED = "mixed"
    COMMON = "common"
    UNKNOWN = "unknown"


class TextDirection(StrEnum):
    RTL = "rtl"
    LTR = "ltr"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class BlockType(StrEnum):
    TITLE = "title"
    INSTRUCTION = "instruction"
    EXERCISE = "exercise"
    SUBQUESTION = "subquestion"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    EQUATION = "equation"
    FIGURE = "figure"
    DIAGRAM = "diagram"
    CAPTION = "caption"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    ANSWER_SPACE = "answer_space"
    STAMP = "stamp"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Checksum(ContractModel):
    algorithm: Literal["sha256"] = "sha256"
    value: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)


class CoordinateSystem(ContractModel):
    unit: Literal["pixel"] = "pixel"
    origin: Literal["top_left"] = "top_left"
    x_axis: Literal["right"] = "right"
    y_axis: Literal["down"] = "down"


class BoundingBox(ContractModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class TableCell(ContractModel):
    cell_id: Identifier
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    bbox: BoundingBox
    raw_text: str = ""
    normalized_text: str = ""


class TableStructure(ContractModel):
    rows: int = Field(ge=1)
    columns: int = Field(ge=1)
    cells: list[TableCell] = Field(min_length=1)

    @model_validator(mode="after")
    def cells_fit_grid(self) -> TableStructure:
        cell_ids = [cell.cell_id for cell in self.cells]
        if len(cell_ids) != len(set(cell_ids)):
            raise ValueError("table cell IDs must be unique")
        for cell in self.cells:
            if cell.row_index + cell.row_span > self.rows:
                raise ValueError(f"table cell {cell.cell_id} exceeds row count")
            if cell.column_index + cell.column_span > self.columns:
                raise ValueError(f"table cell {cell.cell_id} exceeds column count")
        return self


class Confidence(ContractModel):
    score: float = Field(ge=0, le=1)
    calibrated: bool = False
    method: str | None = Field(default=None, min_length=1)


class ProcessingWarning(ContractModel):
    code: Identifier
    message: str = Field(min_length=1)
    severity: Literal["info", "warning", "error"] = "warning"
    stage: str | None = Field(default=None, min_length=1)


class ProcessingError(ContractModel):
    code: Identifier
    message: str = Field(min_length=1)
    stage: str | None = Field(default=None, min_length=1)
    retryable: bool = False


class Provenance(ContractModel):
    kind: Literal[
        "human_annotation",
        "synthetic_generator",
        "system_prediction",
        "native_pdf",
        "ocr",
        "vlm",
        "manual_correction",
        "derived",
    ]
    source: str = Field(min_length=1)
    version: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    stage: str | None = Field(default=None, min_length=1)
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class RecognitionAlternative(ContractModel):
    raw_text: str
    normalized_text: str
    confidence: Confidence
    provenance: Provenance
    reason: str | None = Field(default=None, min_length=1)


class TextSpan(ContractModel):
    span_id: Identifier
    raw_text: str
    normalized_text: str
    search_text: str | None = None
    language: LanguageTag
    script: ScriptTag
    direction: TextDirection
    bbox: BoundingBox
    confidence: Confidence
    provenance: Provenance
    alternatives: list[RecognitionAlternative] = Field(default_factory=list)
    warnings: list[ProcessingWarning] = Field(default_factory=list)


class TextLine(ContractModel):
    line_id: Identifier
    raw_text: str
    normalized_text: str
    search_text: str | None = None
    language: LanguageTag
    script: ScriptTag
    direction: TextDirection
    bbox: BoundingBox
    reading_order_index: int = Field(ge=0)
    confidence: Confidence
    provenance: Provenance
    spans: list[TextSpan] = Field(min_length=1)
    alternatives: list[RecognitionAlternative] = Field(default_factory=list)
    warnings: list[ProcessingWarning] = Field(default_factory=list)


class Block(ContractModel):
    block_id: Identifier
    block_type: BlockType
    bbox: BoundingBox
    reading_order_index: int = Field(ge=0)
    confidence: Confidence
    provenance: Provenance
    lines: list[TextLine] = Field(default_factory=list)
    equation_text: str | None = None
    table: TableStructure | None = None
    alternatives: list[RecognitionAlternative] = Field(default_factory=list)
    warnings: list[ProcessingWarning] = Field(default_factory=list)


class Page(ContractModel):
    page_id: Identifier
    page_index: int = Field(ge=0)
    checksum: Checksum
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    blocks: list[Block] = Field(default_factory=list)
    reading_order: list[Identifier] = Field(default_factory=list)
    provenance: Provenance
    warnings: list[ProcessingWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reading_order(self) -> Page:
        known = {block.block_id for block in self.blocks}
        known.update(line.line_id for block in self.blocks for line in block.lines)
        if len(self.reading_order) != len(set(self.reading_order)):
            raise ValueError("reading_order contains duplicate IDs")
        if unknown := set(self.reading_order) - known:
            raise ValueError(f"reading_order references unknown IDs: {sorted(unknown)}")
        return self


class Document(ContractModel):
    schema_version: str = Field(default=SCHEMA_VERSION, pattern=r"^\d+\.\d+\.\d+$")
    document_id: Identifier
    source_name: str = Field(min_length=1)
    source_kind: Literal["pdf", "image"]
    source_checksum: Checksum
    coordinate_system: CoordinateSystem = Field(default_factory=CoordinateSystem)
    pages: list[Page] = Field(min_length=1)
    pipeline_version: str = SCHEMA_VERSION
    warnings: list[ProcessingWarning] = Field(default_factory=list)
    errors: list[ProcessingError] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)
