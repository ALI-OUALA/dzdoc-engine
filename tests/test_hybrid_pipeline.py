from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

from dzdoc.ingestion import IngestionError
from dzdoc.native_pdf import NativePage, PdfInspection
from dzdoc.ocr import DetectedRegion, Recognition
from dzdoc.pipeline import HybridPipeline, PipelineConfig
from dzdoc.text import assess_native_text


@dataclass
class Inspector:
    def inspect(self, document):
        return PdfInspection(
            page_count=2,
            adapter="test",
            adapter_version="1",
            pages=(
                NativePage(
                    0, "نص أصلي موثوق 123", 600, 800, assess_native_text("نص أصلي موثوق 123")
                ),
                NativePage(1, "", 600, 800, assess_native_text("")),
            ),
        )


class Renderer:
    def __init__(self):
        self.pages = []

    def render(self, document, page_index, dpi=150):
        self.pages.append(page_index)
        return np.full((800, 600, 3), 255, dtype=np.uint8)


class OCR:
    name = "test-ocr"
    version = "1"

    def __init__(self):
        self.detect_calls = 0

    def detect(self, image):
        self.detect_calls += 1
        return [
            DetectedRegion(((350, 50), (550, 50), (550, 90), (350, 90)), 0.9),
            DetectedRegion(((50, 50), (300, 50), (300, 90), (50, 90)), 0.9),
        ]

    def recognize(self, image, region):
        if region.bbox.x > 300:
            return [Recognition("السؤال ١٢", 0.94, "arabic-test", "arabic")]
        return [
            Recognition("Exercice 12", 0.91, "latin-test", "latin"),
            Recognition("ا12", 0.30, "arabic-test", "arabic"),
        ]


def test_native_pages_are_not_rendered_and_ocr_pages_detect_once():
    renderer = Renderer()
    ocr = OCR()
    document = HybridPipeline(pdf_inspector=Inspector(), renderer=renderer, ocr=ocr).process_bytes(
        b"%PDF-1.7", name="mixed.pdf"
    )

    assert renderer.pages == [1]
    assert ocr.detect_calls == 1
    assert document.metadata["native_pages"] == 1
    assert document.metadata["ocr_pages"] == 1
    lines = document.pages[1].blocks
    assert [block.lines[0].normalized_text for block in lines] == ["السؤال ١٢", "Exercice 12"]
    assert document.pages[1].reading_order == [
        document.pages[1].blocks[0].block_id,
        document.pages[1].blocks[0].lines[0].line_id,
        document.pages[1].blocks[1].block_id,
        document.pages[1].blocks[1].lines[0].line_id,
    ]


def test_image_input_uses_real_ocr_boundary():
    renderer = Renderer()
    ocr = OCR()
    buffer = BytesIO()
    Image.new("RGB", (600, 800), "white").save(buffer, format="PNG")
    document = HybridPipeline(renderer=renderer, ocr=ocr).process_bytes(
        buffer.getvalue(), name="page.png"
    )
    assert ocr.detect_calls == 1
    assert document.metadata["ocr_pages"] == 1
    assert document.pages[0].provenance.kind == "ocr"


def test_pdf_render_pixel_limit_is_checked_before_rendering():
    class HugeInspector:
        def inspect(self, document):
            page = NativePage(0, "", 100_000, 100_000, assess_native_text(""))
            return PdfInspection(1, (page,), "test", "1")

    import pytest

    with pytest.raises(IngestionError, match="pixel limit"):
        HybridPipeline(
            PipelineConfig(max_page_pixels=100),
            pdf_inspector=HugeInspector(),
            renderer=Renderer(),
            ocr=OCR(),
        ).process_bytes(b"%PDF-1.7", name="huge.pdf")


def test_native_only_pipeline_does_not_claim_ocr_metadata():
    class NativeOnly:
        def inspect(self, document):
            text = "f(x)=x²+1"
            return PdfInspection(
                1, (NativePage(0, text, 600, 800, assess_native_text(text)),), "test", "1"
            )

    document = HybridPipeline(pdf_inspector=NativeOnly()).process_bytes(
        b"%PDF-1.7", name="native.pdf"
    )
    block = document.pages[0].blocks[0]
    assert block.block_type.value == "equation"
    assert block.equation_text == "f(x)=x²+1"
    assert "ocr_adapter" not in document.metadata
