from dataclasses import dataclass

import numpy as np

from dzdoc.native_pdf import NativePage, PdfInspection
from dzdoc.pipeline import HybridPipeline
from dzdoc.text import assess_native_text


@dataclass
class FakeInspector:
    def inspect(self, document):
        return PdfInspection(
            page_count=2,
            adapter="test-fake",
            adapter_version="1",
            pages=(
                NativePage(0, "فاتورة 123 EUR", 100, 200, assess_native_text("فاتورة 123 EUR")),
                NativePage(1, "bad\ufffdtext", 100, 200, assess_native_text("bad\ufffdtext")),
            ),
        )


def test_fake_pipeline_preserves_native_and_records_ocr_route():
    class Renderer:
        def render(self, document, page_index, dpi=150):
            return np.full((200, 100, 3), 255, dtype=np.uint8)

    class EmptyOcr:
        name = "empty-test"
        version = "1"

        def detect(self, image):
            return []

    document = HybridPipeline(
        pdf_inspector=FakeInspector(), renderer=Renderer(), ocr=EmptyOcr()
    ).process_bytes(b"%PDF-1.7", name="x.pdf")
    assert len(document.pages[0].blocks) == 1
    assert document.pages[0].blocks[0].lines[0].raw_text.startswith("فاتورة")
    assert document.pages[1].blocks == []
    assert document.pages[1].warnings[0].code == "no_text_detected"
