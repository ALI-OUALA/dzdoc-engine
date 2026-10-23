from pathlib import Path

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore


def _runtime(tmp_path: Path):
    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path / 'service.db'}",
        object_root=tmp_path / "objects",
        bootstrap_token="bootstrap-test-token",
    )
    database = Database(settings.database_url)
    database.create_schema()
    store = LocalObjectStore(settings.object_root)
    return settings, database, store


def test_deduplicated_storage_deletion(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    service = DocumentService(database, store, settings)
    _tenant, token = service.bootstrap()
    principal = service.authenticate(token)

    doc1, _, _ = service.submit(
        principal, b"%PDF-1.7 same_content", filename="doc1.pdf", idempotency_key=None
    )
    doc2, _, _ = service.submit(
        principal, b"%PDF-1.7 same_content", filename="doc2.pdf", idempotency_key=None
    )

    assert doc1.source_object_key == doc2.source_object_key
    assert store.exists(doc1.source_object_key)

    # Deleting doc1 should not delete the shared object store file
    service.delete_document(principal, doc1.id)
    assert store.exists(doc2.source_object_key)

    # Deleting doc2 should finally delete the object store file since no references exist
    service.delete_document(principal, doc2.id)
    assert not store.exists(doc2.source_object_key)
