"""Native-first deterministic Arabic-French OCR cascade."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .ingestion import DocumentInput, IngestionError, SecureIngestor
from .layout import classify_block_type
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
    RecognitionAlternative,
    TextLine,
    TextSpan,
)
from .native_pdf import NativePage, NativePdfInspector, PdfInspection
from .ocr import (
    PaddleOcrEngine,
    fuse_recognitions,
    order_recognized_regions,
)
from .rendering import PdfiumRenderer, decode_image
from .text import classify_text, normalization_warnings, normalize_display, normalize_search


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    max_bytes: int = 50 * 1024 * 1024
    pipeline_version: str = "0.2.0"
    render_dpi: int = 150
    ambiguity_margin: float = 0.08
    max_pages: int = 200
    max_page_pixels: int = 40_000_000

    def __post_init__(self) -> None:
        if self.max_bytes <= 0 or self.max_pages <= 0 or self.max_page_pixels <= 0:
            raise ValueError("pipeline limits must be positive")
        if self.render_dpi <= 0:
            raise ValueError("render_dpi must be positive")
        if not 0 <= self.ambiguity_margin <= 1:
            raise ValueError("ambiguity_margin must be between 0 and 1")


class HybridPipeline:
    """Preserve trustworthy native pages and OCR only rejected pages."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        pdf_inspector=None,
        renderer=None,
        ocr=None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.ingestor = SecureIngestor(max_bytes=self.config.max_bytes)
        self.pdf_inspector = pdf_inspector or NativePdfInspector(max_pages=self.config.max_pages)
        self.renderer = renderer or PdfiumRenderer()
        self._ocr = ocr

    @property
    def ocr(self):
        """Build the optional OCR adapter only if an OCR page is actually needed."""

        if self._ocr is None:
            self._ocr = PaddleOcrEngine()
        return self._ocr

    def process_path(self, source: str | Path) -> Document:
        return self.process_input(self.ingestor.load(source))

    def process_bytes(self, data: bytes, *, name: str = "document.bin") -> Document:
        return self.process_input(self.ingestor.from_bytes(data, name=name))

    def process_input(self, source: DocumentInput) -> Document:
        started = time.perf_counter()
        document_id = _safe_id(source.sha256[:16])
        if source.kind == "pdf":
            inspection: PdfInspection = self.pdf_inspector.inspect(source)
            if inspection.page_count > self.config.max_pages:
                raise IngestionError(f"PDF exceeds {self.config.max_pages} page limit")
            if inspection.page_count != len(inspection.pages):
                raise IngestionError("PDF inspection returned an inconsistent page count")
            built_pages = []
            for native in inspection.pages:
                if native.quality.accepted:
                    built_pages.append(self._page_from_native(source, document_id, native))
                else:
                    scale = self.config.render_dpi / 72
                    if native.width * native.height * scale * scale > self.config.max_page_pixels:
                        raise IngestionError("rendered PDF page exceeds pixel limit")
                    image = self.renderer.render(
                        source, native.page_index, dpi=self.config.render_dpi
                    )
                    built_pages.append(
                        self._page_from_ocr(source, document_id, native.page_index, image)
                    )
            pages = tuple(built_pages)
            metadata = {
                "native_pdf_adapter": inspection.adapter,
                "native_pdf_adapter_version": inspection.adapter_version,
                "native_pages": sum(page.provenance.kind == "native_pdf" for page in pages),
                "ocr_pages": sum(page.provenance.kind == "ocr" for page in pages),
            }
        else:
            pages = (
                self._page_from_ocr(
                    source,
                    document_id,
                    0,
                    decode_image(source, max_pixels=self.config.max_page_pixels),
                ),
            )
            metadata = {"native_pages": 0, "ocr_pages": 1}
        metadata["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        if metadata["ocr_pages"]:
            ocr = self.ocr
            metadata["ocr_adapter"] = getattr(ocr, "name", type(ocr).__name__)
            metadata["ocr_adapter_version"] = getattr(ocr, "version", "unknown")
            if revisions := getattr(ocr, "asset_revisions", None):
                metadata["ocr_asset_revisions"] = revisions
            if adapter_metadata := getattr(ocr, "metadata", None):
                metadata["ocr_model"] = adapter_metadata.upstream_model or "unknown"
        return Document(
            document_id=document_id,
            source_name=source.name,
            source_kind=source.kind,
            source_checksum=Checksum(value=source.sha256, size_bytes=source.size_bytes),
            pages=pages,
            pipeline_version=self.config.pipeline_version,
            metadata=metadata,
        )

    def _page_from_ocr(self, source, document_id: str, page_index: int, image) -> Page:
        if hasattr(image, "shape"):
            height, width = int(image.shape[0]), int(image.shape[1])
        else:
            width, height = int(image.width), int(image.height)
        ocr = self.ocr
        detected = list(ocr.detect(image) or [])
        recognized = []
        for region in detected:
            candidates = [
                candidate
                for candidate in (ocr.recognize(image, region) or [])
                if candidate.text.strip()
            ]
            if candidates:
                recognized.append(
                    (
                        region,
                        fuse_recognitions(
                            candidates, ambiguity_margin=self.config.ambiguity_margin
                        ),
                    )
                )
        ordered = order_recognized_regions(recognized)
        blocks: list[Block] = []
        reading_order: list[str] = []
        for index, (region, fused) in enumerate(ordered):
            raw = fused.selected.text
            normalized = normalize_display(raw)
            language, script, direction = classify_text(normalized)
            provenance = Provenance(
                kind="ocr",
                source=fused.selected.adapter,
                version=getattr(self.ocr, "version", "unknown"),
                model=fused.selected.adapter,
                stage="recognition",
                details={"detection_confidence": round(region.confidence, 6)},
            )
            confidence = Confidence(
                score=max(0.0, min(1.0, fused.confidence * region.confidence)),
                calibrated=False,
                method="recognizer_script_detection_fusion",
            )
            alternatives = [
                RecognitionAlternative(
                    raw_text=value.text,
                    normalized_text=normalize_display(value.text),
                    confidence=Confidence(
                        score=value.confidence, calibrated=False, method="recognizer_native"
                    ),
                    provenance=Provenance(
                        kind="ocr",
                        source=value.adapter,
                        version=getattr(self.ocr, "version", "unknown"),
                        model=value.adapter,
                        stage="candidate_fusion",
                    ),
                    reason="non_selected_candidate",
                )
                for value in fused.alternatives
            ]
            bbox = _clamp_bbox(region.bbox, width, height)
            block_type = classify_block_type(normalized, bbox, page_width=width, page_height=height)
            text_warnings = normalization_warnings(raw)
            span = TextSpan(
                span_id=f"p{page_index:04d}-s{index:04d}",
                raw_text=raw,
                normalized_text=normalized,
                search_text=normalize_search(normalized),
                language=language,
                script=script,
                direction=direction,
                bbox=bbox,
                confidence=confidence,
                provenance=provenance,
                alternatives=alternatives,
                warnings=[*fused.warnings, *text_warnings],
            )
            line = TextLine(
                line_id=f"p{page_index:04d}-l{index:04d}",
                raw_text=raw,
                normalized_text=normalized,
                search_text=span.search_text,
                language=language,
                script=script,
                direction=direction,
                bbox=bbox,
                reading_order_index=index,
                confidence=confidence,
                provenance=provenance,
                spans=[span],
                alternatives=alternatives,
                warnings=[*fused.warnings, *text_warnings],
            )
            block = Block(
                block_id=f"p{page_index:04d}-b{index:04d}",
                block_type=block_type,
                bbox=bbox,
                reading_order_index=index,
                confidence=confidence,
                provenance=provenance,
                lines=[line],
                equation_text=normalized if block_type == BlockType.EQUATION else None,
                alternatives=alternatives,
                warnings=[*fused.warnings, *text_warnings],
            )
            blocks.append(block)
            reading_order.extend([block.block_id, line.line_id])
        warnings = []
        if not blocks:
            warnings.append(
                ProcessingWarning(
                    code="no_text_detected" if not detected else "recognition_failed",
                    message=(
                        "The OCR detector found no text regions."
                        if not detected
                        else "The OCR detector found regions but recognition returned no text."
                    ),
                    stage="text_detection" if not detected else "recognition",
                )
            )
        return Page(
            page_id=f"{document_id}-p{page_index:04d}",
            page_index=page_index,
            checksum=_page_checksum(source, page_index, "ocr"),
            width=width,
            height=height,
            blocks=blocks,
            reading_order=reading_order,
            provenance=Provenance(
                kind="ocr",
                source=getattr(self.ocr, "name", type(self.ocr).__name__),
                version=getattr(self.ocr, "version", "unknown"),
                stage="hybrid_pipeline",
                details={"detector_passes": 1, "region_count": len(blocks)},
            ),
            warnings=warnings,
        )

    def _page_from_native(
        self, source: DocumentInput, document_id: str, native: NativePage
    ) -> Page:
        if native.quality.accepted:
            width = max(1, round(native.width * self.config.render_dpi / 72))
            height = max(1, round(native.height * self.config.render_dpi / 72))
            block, line = _native_text_units(native.text, native.page_index, width, height)
            return Page(
                page_id=f"{document_id}-p{native.page_index:04d}",
                page_index=native.page_index,
                checksum=_page_checksum(source, native),
                width=width,
                height=height,
                blocks=[block],
                reading_order=[block.block_id, line.line_id],
                provenance=Provenance(
                    kind="native_pdf",
                    source="pypdfium2",
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
    raw = text
    normalized = normalize_display(raw)
    search = normalize_search(normalized)
    language, script, direction = classify_text(normalized)
    provenance = Provenance(
        kind="native_pdf", source="pypdfium2", version="native-text", stage="extraction"
    )
    confidence = Confidence(score=0.95, calibrated=False, method="native_quality_gate")
    bbox = BoundingBox(x=0, y=0, width=max(1, width), height=max(1, height))
    block_type = classify_block_type(normalized, bbox, page_width=width, page_height=height)
    text_warnings = normalization_warnings(raw)
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
        warnings=text_warnings,
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
        warnings=text_warnings,
    )
    block = Block(
        block_id=f"p{page_index:04d}-b0000",
        block_type=block_type,
        bbox=bbox,
        reading_order_index=0,
        confidence=confidence,
        provenance=provenance,
        lines=[line],
        equation_text=normalized if block_type == BlockType.EQUATION else None,
        warnings=text_warnings,
    )
    return block, line


def _page_checksum(source: DocumentInput, page: NativePage | int, reason: str = "") -> Checksum:
    index = page.page_index if isinstance(page, NativePage) else page
    evidence = f"{source.sha256}:{index}:{reason}".encode()
    return Checksum(value=hashlib.sha256(evidence).hexdigest(), size_bytes=len(evidence))


def _safe_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9._:-]+", "-", value)
    return result.strip("-") or "document"


def _clamp_bbox(bbox: BoundingBox, width: int, height: int) -> BoundingBox:
    x = min(max(0.0, bbox.x), max(0.0, width - 1.0))
    y = min(max(0.0, bbox.y), max(0.0, height - 1.0))
    right = min(float(width), max(x + 1.0, bbox.x + bbox.width))
    bottom = min(float(height), max(y + 1.0, bbox.y + bbox.height))
    return BoundingBox(x=x, y=y, width=max(1.0, right - x), height=max(1.0, bottom - y))


# Compatibility for Phase 1 callers. New code should use HybridPipeline.
FakePipeline = HybridPipeline
