import pytest

from dzdoc.ingestion import SecureIngestor
from dzdoc.native_pdf import NativePdfInspector
from dzdoc.rendering import PdfiumRenderer

pytest.importorskip("pypdfium2")
pytest.importorskip("numpy")


def _minimal_text_pdf() -> bytes:
    content = b"BT /F1 18 Tf 72 720 Td (Bonjour 123) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(payload)


def test_pdfium_extracts_native_text_and_renders_pixels():
    document = SecureIngestor().from_bytes(_minimal_text_pdf(), name="native.pdf")
    inspection = NativePdfInspector().inspect(document)
    assert inspection.adapter == "pypdfium2"
    assert inspection.pages[0].text.strip() == "Bonjour 123"
    assert inspection.pages[0].quality.accepted
    image = PdfiumRenderer().render(document, 0, dpi=72)
    assert image.shape == (792, 612, 3)
