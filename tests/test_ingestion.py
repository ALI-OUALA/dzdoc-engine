import pytest

from dzdoc.ingestion import IngestionError, SecureIngestor


def test_signature_and_fingerprint():
    document = SecureIngestor().from_bytes(b"%PDF-1.7\n", name="x.pdf")
    assert document.kind == "pdf"
    assert len(document.sha256) == 64


def test_invalid_signature_rejected():
    with pytest.raises(IngestionError):
        SecureIngestor().from_bytes(b"not a document")


def test_size_limit_rejected():
    with pytest.raises(IngestionError):
        SecureIngestor(max_bytes=4).from_bytes(b"%PDF-1.7")


def test_non_bytes_input_rejected():
    with pytest.raises(IngestionError, match="bytes-like"):
        SecureIngestor().from_bytes("%PDF-1.7")
