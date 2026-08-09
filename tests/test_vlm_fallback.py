from io import BytesIO

from PIL import Image

from dzdoc.fallback import VlmFallbackResult
from dzdoc.ocr import DetectedRegion, Recognition
from dzdoc.pipeline import HybridPipeline, PipelineConfig


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (500, 180), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class LowConfidenceOcr:
    name = "low-confidence-ocr"
    version = "1"

    def __init__(self, confidence: float = 0.35, text: str = "TTC 1190") -> None:
        self.confidence = confidence
        self.text = text

    def detect(self, image):
        return [DetectedRegion(((20, 20), (480, 20), (480, 150), (20, 150)), 0.95)]

    def recognize(self, image, region):
        return [Recognition(self.text, self.confidence, "fixture-ocr", "latin")]


class Fallback:
    name = "fixture-vlm"
    version = "1"
    model_name = "fixture/document-vlm"
    model_revision = "a" * 40

    def __init__(self, text: str = "Total TTC: 1 190,00 DZD") -> None:
        self.text = text
        self.calls = 0

    def resolve(self, image, region):
        self.calls += 1
        return VlmFallbackResult(
            text=self.text,
            confidence=0.86,
            raw_output={"text": self.text},
            prompt_label="ocr",
            decoding={"temperature": 0.0},
        )


def test_low_confidence_region_uses_traceable_vlm_fallback() -> None:
    fallback = Fallback()
    document = HybridPipeline(
        PipelineConfig(fallback_enabled=True, fallback_confidence_threshold=0.6),
        ocr=LowConfidenceOcr(),
        fallback=fallback,
    ).process_bytes(_png(), name="invoice.png")

    block = document.pages[0].blocks[0]
    assert fallback.calls == 1
    assert block.lines[0].normalized_text == "Total TTC: 1 190,00 DZD"
    assert block.provenance.kind == "vlm"
    assert block.alternatives[0].raw_text == "TTC 1190"
    event = document.pages[0].events[0]
    assert event.status == "accepted"
    assert event.trigger == "low_confidence"
    assert event.model_revision == "a" * 40
    assert document.metadata["vlm_accepted_regions"] == 1


def test_high_confidence_region_never_calls_fallback() -> None:
    fallback = Fallback()
    document = HybridPipeline(
        PipelineConfig(fallback_enabled=True, fallback_confidence_threshold=0.6),
        ocr=LowConfidenceOcr(confidence=0.98, text="Total TTC: 1 190,00 DZD"),
        fallback=fallback,
    ).process_bytes(_png(), name="invoice.png")

    assert fallback.calls == 0
    assert document.pages[0].events == []


def test_digit_conflict_rejects_vlm_without_overwriting_evidence() -> None:
    fallback = Fallback(text="Total TTC: 1 199,00 DZD")
    document = HybridPipeline(
        PipelineConfig(fallback_enabled=True, fallback_confidence_threshold=0.6),
        ocr=LowConfidenceOcr(text="Total TTC: 1 190,00 DZD"),
        fallback=fallback,
    ).process_bytes(_png(), name="invoice.png")

    block = document.pages[0].blocks[0]
    assert block.lines[0].normalized_text == "Total TTC: 1 190,00 DZD"
    assert block.provenance.kind == "ocr"
    assert document.pages[0].events[0].status == "rejected"
    assert document.pages[0].events[0].details["reason"] == "digit_conflict"
