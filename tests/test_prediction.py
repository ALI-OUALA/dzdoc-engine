from dataclasses import dataclass

from dzdoc.exporters import to_prediction
from dzdoc.native_pdf import NativePage, PdfInspection
from dzdoc.pipeline import FakePipeline
from dzdoc.text import assess_native_text


@dataclass
class Inspector:
    def inspect(self, document):
        text = "Bon de commande 2026"
        return PdfInspection(
            1, (NativePage(0, text, 100, 100, assess_native_text(text)),), "fake", "1"
        )


def test_prediction_contract_shape():
    document = FakePipeline(pdf_inspector=Inspector()).process_bytes(b"%PDF-1.7", name="x.pdf")
    prediction = to_prediction(document, dataset_id="synthetic-smoke", dataset_revision="0.1.0")
    assert prediction["schema_version"] == "1.0.0"
    assert prediction["samples"][0]["page"]["page_id"] == document.pages[0].page_id
    assert prediction["samples"][0]["page"]["checksum"]["algorithm"] == "sha256"
