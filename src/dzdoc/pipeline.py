"""Native-first deterministic Arabic-French OCR cascade."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .fallback import validate_fallback
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
    ProcessingEvent,
    ProcessingWarning,
    Provenance,
    RecognitionAlternative,
    TextLine,
    TextSpan,
)
from .native_pdf import NativePage, NativePdfInspector, PdfInspection
from .ocr import (
    FusedRecognition,
    PaddleOcrEngine,
    candidate_score,
    fuse_recognitions,
    order_recognized_regions,
)
from .rendering import PdfiumRenderer, decode_image
from .text import classify_text, normalization_warnings, normalize_display, normalize_search

type MetadataValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    max_bytes: int = 50 * 1024 * 1024
    pipeline_version: str = "0.2.0"
    render_dpi: int = 150
    ambiguity_margin: float = 0.08
    max_pages: int = 200
    max_page_pixels: int = 40_000_000
    fallback_enabled: bool = False
    fallback_confidence_threshold: float = 0.58
    fallback_minimum_gain: float = 0.08
    fallback_max_regions_per_page: int = 1
    fallback_max_output_chars: int = 4096

    def __post_init__(self) -> None:
        if self.max_bytes <= 0 or self.max_pages <= 0 or self.max_page_pixels <= 0:
            raise ValueError("pipeline limits must be positive")
        if self.render_dpi <= 0:
            raise ValueError("render_dpi must be positive")
        if not 0 <= self.ambiguity_margin <= 1:
            raise ValueError("ambiguity_margin must be between 0 and 1")
        if not 0 <= self.fallback_confidence_threshold <= 1:
            raise ValueError("fallback confidence threshold must be between 0 and 1")
        if not 0 <= self.fallback_minimum_gain <= 1:
            raise ValueError("fallback minimum gain must be between 0 and 1")
        if self.fallback_max_regions_per_page <= 0 or self.fallback_max_output_chars <= 0:
            raise ValueError("fallback limits must be positive")


class HybridPipeline:
    """Preserve trustworthy native pages and OCR only rejected pages."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        pdf_inspector=None,
        renderer=None,
        ocr=None,
        fallback=None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.ingestor = SecureIngestor(max_bytes=self.config.max_bytes)
        self.pdf_inspector = pdf_inspector or NativePdfInspector(max_pages=self.config.max_pages)
        self.renderer = renderer or PdfiumRenderer()
        self._ocr = ocr
        self.fallback = fallback

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
            built_pages: list[Page] = []
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
            pages = built_pages
            metadata: dict[str, MetadataValue] = {
                "native_pdf_adapter": inspection.adapter,
                "native_pdf_adapter_version": inspection.adapter_version,
                "native_pages": sum(page.provenance.kind == "native_pdf" for page in pages),
                "ocr_pages": sum(page.provenance.kind == "ocr" for page in pages),
            }
        else:
            pages = [
                self._page_from_ocr(
                    source,
                    document_id,
                    0,
                    decode_image(source, max_pixels=self.config.max_page_pixels),
                ),
            ]
            metadata = {"native_pages": 0, "ocr_pages": 1}
        metadata["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        events = [event for page in pages for event in page.events]
        if events:
            metadata["vlm_attempted_regions"] = len(events)
            metadata["vlm_accepted_regions"] = sum(event.status == "accepted" for event in events)
            metadata["vlm_rejected_regions"] = sum(event.status == "rejected" for event in events)
            metadata["vlm_failed_regions"] = sum(event.status == "failed" for event in events)
            metadata["vlm_adapter"] = getattr(self.fallback, "name", "unknown")
            metadata["vlm_adapter_version"] = getattr(self.fallback, "version", "unknown")
            metadata["vlm_model"] = getattr(self.fallback, "model_name", "unknown")
            metadata["vlm_model_revision"] = getattr(self.fallback, "model_revision", "unknown")
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
        events: list[ProcessingEvent] = []
        fallback_attempts = 0
        for region_index, region in enumerate(detected):
            candidates = [
                candidate
                for candidate in (ocr.recognize(image, region) or [])
                if candidate.text.strip()
            ]
            if candidates:
                fused = fuse_recognitions(candidates, ambiguity_margin=self.config.ambiguity_margin)
                trigger = _fallback_trigger(fused, self.config)
                if trigger and self.fallback is not None and self.config.fallback_enabled:
                    if fallback_attempts >= self.config.fallback_max_regions_per_page:
                        events.append(
                            _fallback_event(
                                page_index,
                                region_index,
                                self.fallback,
                                "skipped",
                                trigger,
                                fused.confidence,
                                None,
                                0.0,
                                {"reason": "page_region_limit"},
                            )
                        )
                    else:
                        fallback_attempts += 1
                        fused, event = self._run_fallback(
                            image, region, page_index, region_index, fused, trigger
                        )
                        events.append(event)
                recognized.append((region, fused))
        ordered = order_recognized_regions(recognized)
        blocks: list[Block] = []
        reading_order: list[str] = []
        for index, (region, fused) in enumerate(ordered):
            raw = fused.selected.text
            normalized = normalize_display(raw)
            language, script, direction = classify_text(normalized)
            provenance = Provenance(
                kind=fused.selected.kind,
                source=fused.selected.adapter,
                version=(
                    getattr(self.fallback, "version", "unknown")
                    if fused.selected.kind == "vlm"
                    else getattr(self.ocr, "version", "unknown")
                ),
                model=fused.selected.model or fused.selected.adapter,
                stage="recognition",
                details={
                    "detection_confidence": round(region.confidence, 6),
                    **(fused.selected.details or {}),
                },
            )
            confidence = Confidence(
                score=max(0.0, min(1.0, fused.confidence * region.confidence)),
                calibrated=False,
                method=(
                    "guarded_vlm_validation"
                    if fused.selected.kind == "vlm"
                    else "recognizer_script_detection_fusion"
                ),
            )
            alternatives = [
                RecognitionAlternative(
                    raw_text=value.text,
                    normalized_text=normalize_display(value.text),
                    confidence=Confidence(
                        score=value.confidence, calibrated=False, method="recognizer_native"
                    ),
                    provenance=Provenance(
                        kind=value.kind,
                        source=value.adapter,
                        version=(
                            getattr(self.fallback, "version", "unknown")
                            if value.kind == "vlm"
                            else getattr(self.ocr, "version", "unknown")
                        ),
                        model=value.model or value.adapter,
                        stage="candidate_fusion",
                        details=value.details or {},
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
            events=events,
        )

    def _run_fallback(
        self, image, region, page_index: int, region_index: int, fused, trigger: str
    ) -> tuple[FusedRecognition, ProcessingEvent]:
        started = time.perf_counter()
        before = fused.confidence
        try:
            assert self.fallback is not None
            result = self.fallback.resolve(image, region)
            decision = validate_fallback(
                fused,
                result,
                adapter=getattr(self.fallback, "name", type(self.fallback).__name__),
                model=getattr(self.fallback, "model_name", "unknown"),
                model_revision=getattr(self.fallback, "model_revision", "unknown"),
                max_output_chars=self.config.fallback_max_output_chars,
                minimum_gain=self.config.fallback_minimum_gain,
            )
            elapsed = (time.perf_counter() - started) * 1000
            details: dict[str, MetadataValue] = {
                "reason": decision.reason,
                "prompt_label": result.prompt_label,
                "raw_output_json": json.dumps(
                    result.raw_output, ensure_ascii=False, sort_keys=True
                )[: self.config.fallback_max_output_chars],
                **result.decoding,
            }
            if not decision.accepted or decision.recognition is None:
                return fused, _fallback_event(
                    page_index,
                    region_index,
                    self.fallback,
                    "rejected",
                    trigger,
                    before,
                    before,
                    elapsed,
                    details,
                )
            selected = decision.recognition
            warning = ProcessingWarning(
                code="vlm_fallback_used",
                message="Validated region-level VLM output replaced low-confidence OCR.",
                severity="info",
                stage="guarded_vlm_fallback",
            )
            updated = FusedRecognition(
                selected=selected,
                alternatives=(fused.selected, *fused.alternatives),
                confidence=candidate_score(selected),
                warnings=(*fused.warnings, warning),
            )
            return updated, _fallback_event(
                page_index,
                region_index,
                self.fallback,
                "accepted",
                trigger,
                before,
                updated.confidence,
                elapsed,
                details,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return fused, _fallback_event(
                page_index,
                region_index,
                self.fallback,
                "failed",
                trigger,
                before,
                before,
                elapsed,
                {"reason": type(exc).__name__},
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


def _fallback_trigger(fused: FusedRecognition, config: PipelineConfig) -> str | None:
    if fused.confidence < config.fallback_confidence_threshold:
        return "low_confidence"
    warning_codes = {warning.code for warning in fused.warnings}
    if "digit_disagreement" in warning_codes:
        return "digit_disagreement"
    if "ambiguous_recognition" in warning_codes:
        return "ambiguous_recognition"
    return None


def _fallback_event(
    page_index: int,
    region_index: int,
    fallback,
    status: Literal["attempted", "accepted", "rejected", "failed", "skipped"],
    trigger: str,
    confidence_before: float,
    confidence_after: float | None,
    duration_ms: float,
    details: dict[str, MetadataValue],
) -> ProcessingEvent:
    return ProcessingEvent(
        event_id=f"p{page_index:04d}-fallback-{region_index:04d}",
        stage="guarded_vlm_fallback",
        status=status,
        trigger=trigger,
        adapter_name=getattr(fallback, "name", type(fallback).__name__),
        adapter_version=getattr(fallback, "version", "unknown"),
        model_name=getattr(fallback, "model_name", None),
        model_revision=getattr(fallback, "model_revision", None),
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        duration_ms=duration_ms,
        details=details,
    )


# Compatibility for Phase 1 callers. New code should use HybridPipeline.
FakePipeline = HybridPipeline
