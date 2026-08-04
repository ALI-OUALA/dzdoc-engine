"""Deterministic Phase 1 pipeline with explicit OCR escalation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .ingestion import DocumentInput, SecureIngestor
from .models import (
    Block,
    BlockType,
    BoundingBox,
    Checksum,
    Confidence,
    Document,
    Page,
    ProcessingWarning,
    Provenance,
    TextLine,
    TextSpan,
)
from .native_pdf import NativePage, NativePdfInspector, PdfInspection
from .text import classify_text, normalize_display, normalize_search


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    max_bytes: int = 50 * 1024 * 1024
    pipeline_version: str = "0.1.0"


class FakePipeline:
    """Native-first pipeline; OCR/layout stages remain explicit extension points."""

    def __init__(self, config: PipelineConfig | None = None, *, pdf_inspector=None) -> None:
        self.config = config or PipelineConfig()
        self.ingestor = SecureIngestor(max_bytes=self.config.max_bytes)
        self.pdf_inspector = pdf_inspector or NativePdfInspector()

    def process_path(self, source: str | Path) -> Document:
        return self.process_input(self.ingestor.load(source))

    def process_bytes(self, data: bytes, *, name: str = "document.bin") -> Document:
        return self.process_input(self.ingestor.from_bytes(data, name=name))

    def process_input(self, source: DocumentInput) -> Document:
        document_id = _safe_id(source.sha256[:16])
        if source.kind == "pdf":
            inspection: PdfInspection = self.pdf_inspector.inspect(source)
            pages = tuple(
                self._page_from_native(source, document_id, native) for native in inspection.pages
            )
            metadata = {
                "native_pdf_adapter": inspection.adapter,
                "native_pdf_adapter_version": inspection.adapter_version,
                "ocr_required_pages": sum(
                    any(warning.code == "ocr_required" for warning in page.warnings)
                    for page in pages
                ),
            }
        else:
            width, height = _image_dimensions(source.data)
            pages = (self._empty_page(source, document_id, 0, width, height, "image_requires_ocr"),)
            metadata = {"ocr_required_pages": 1}
        return Document(
            document_id=document_id,
            source_name=source.name,
            source_kind=source.kind,
            source_checksum=Checksum(value=source.sha256, size_bytes=source.size_bytes),
            pages=pages,
            pipeline_version=self.config.pipeline_version,
            metadata=metadata,
        )

    def _page_from_native(
        self, source: DocumentInput, document_id: str, native: NativePage
    ) -> Page:
        if native.quality.accepted:
            block, line = _native_text_units(
                native.text, native.page_index, native.width, native.height
            )
            return Page(
                page_id=f"{document_id}-p{native.page_index:04d}",
                page_index=native.page_index,
                checksum=_page_checksum(source, native),
                width=native.width,
                height=native.height,
                blocks=[block],
                reading_order=[block.block_id, line.line_id],
                provenance=Provenance(
                    kind="native_pdf",
                    source="pymupdf",
                    version="native-text",
                    stage="pdf_inspection",
                ),
            )
        return self._empty_page(
            source,
            document_id,
            native.page_index,
            native.width,
            native.height,
            native.quality.reason,
        )

    def _empty_page(
        self,
        source: DocumentInput,
        document_id: str,
        page_index: int,
        width: int,
        height: int,
        reason: str,
    ) -> Page:
        warning = ProcessingWarning(
            code="ocr_required",
            message=f"No trusted native text available: {reason}; OCR stage not installed.",
            severity="warning",
            stage="native_text_quality_gate",
        )
        return Page(
            page_id=f"{document_id}-p{page_index:04d}",
            page_index=page_index,
            checksum=_page_checksum(source, page_index, reason),
            width=width,
            height=height,
            provenance=Provenance(
                kind="derived",
                source="dzdoc.fake_pipeline",
                version=self.config.pipeline_version,
                stage="routing",
            ),
            warnings=[warning],
        )


def _native_text_units(
    text: str, page_index: int, width: int, height: int
) -> tuple[Block, TextLine]:
    raw = text.strip()
    normalized = normalize_display(raw)
    search = normalize_search(normalized)
    language, script, direction = classify_text(normalized)
    provenance = Provenance(
        kind="native_pdf", source="pymupdf", version="native-text", stage="extraction"
    )
    confidence = Confidence(score=0.95, calibrated=False, method="native_quality_gate")
    bbox = BoundingBox(x=0, y=0, width=max(1, width), height=max(1, height))
    span = TextSpan(
        span_id=f"p{page_index:04d}-s0000",
        raw_text=raw,
        normalized_text=normalized,
        search_text=search,
        language=language,
        script=script,
        direction=direction,
        bbox=bbox,
        confidence=confidence,
        provenance=provenance,
    )
    line = TextLine(
        line_id=f"p{page_index:04d}-l0000",
        raw_text=raw,
        normalized_text=normalized,
        search_text=search,
        language=language,
        script=script,
        direction=direction,
        bbox=bbox,
        reading_order_index=0,
        confidence=confidence,
        provenance=provenance,
        spans=[span],
    )
    block = Block(
        block_id=f"p{page_index:04d}-b0000",
        block_type=BlockType.PARAGRAPH,
        bbox=bbox,
        reading_order_index=0,
        confidence=confidence,
        provenance=provenance,
        lines=[line],
    )
    return block, line


def _page_checksum(source: DocumentInput, page: NativePage | int, reason: str = "") -> Checksum:
    index = page.page_index if isinstance(page, NativePage) else page
    evidence = f"{source.sha256}:{index}:{reason}".encode()
    return Checksum(value=hashlib.sha256(evidence).hexdigest(), size_bytes=len(evidence))


def _safe_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9._:-]+", "-", value)
    return result.strip("-") or "document"


def _image_dimensions(data: bytes) -> tuple[int, int]:
    try:
        from PIL import Image  # type: ignore[import-not-found]

        with Image.open(__import__("io").BytesIO(data)) as image:
            return max(1, int(image.width)), max(1, int(image.height))
    except Exception:
        return 1, 1
