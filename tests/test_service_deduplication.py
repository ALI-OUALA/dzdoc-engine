from pathlib import Path

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database, StoredDocument
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


PDF_BYTES = b"%PDF-1.4\n" + b"A" * 100


def test_deleting_document_does_not_delete_shared_object(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    service = DocumentService(database, store, settings)
    tenant, token = service.bootstrap()

    principal = service.authenticate(token)
    assert principal is not None

    doc1, job1, created1 = service.submit(
        principal, PDF_BYTES, filename="file1.pdf", idempotency_key="idemp1-0000"
    )
    doc2, job2, created2 = service.submit(
        principal, PDF_BYTES, filename="file2.pdf", idempotency_key="idemp2-0000"
    )

    assert doc1.source_object_key == doc2.source_object_key
    assert store.exists(doc1.source_object_key)

    # Delete doc1
    deleted = service.delete_document(principal, doc1.id)
    assert deleted is True

    # Object store should still have the content since doc2 uses it
    assert store.exists(doc2.source_object_key)

    # Delete doc2
    service.delete_document(principal, doc2.id)

    # Now it should be gone
    assert not store.exists(doc2.source_object_key)


def test_purging_document_does_not_delete_shared_object(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    service = DocumentService(database, store, settings)
    tenant, token = service.bootstrap()

    principal = service.authenticate(token)
    assert principal is not None

    PDF_BYTES_2 = b"%PDF-1.4\n" + b"B" * 100

    doc1, job1, created1 = service.submit(
        principal, PDF_BYTES_2, filename="file1.pdf", idempotency_key="idemp3-0000"
    )
    doc2, job2, created2 = service.submit(
        principal, PDF_BYTES_2, filename="file2.pdf", idempotency_key="idemp4-0000"
    )

    from datetime import timedelta

    from dzdoc_service.db import utcnow

    with database.session() as session:
        d1 = session.get(StoredDocument, doc1.id)
        assert d1 is not None
        d1.delete_after = utcnow() - timedelta(days=1)
        session.commit()

    count = service.purge_expired()
    assert count == 1

    # Object store should still have the content since doc2 uses it
    assert store.exists(doc2.source_object_key)

    with database.session() as session:
        d2 = session.get(StoredDocument, doc2.id)
        assert d2 is not None
        d2.delete_after = utcnow() - timedelta(days=1)
        session.commit()

    count = service.purge_expired()
    assert count == 1

    # Now it should be gone
    assert not store.exists(doc2.source_object_key)
