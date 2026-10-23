from datetime import timedelta
from pathlib import Path

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database, StoredDocument, utcnow
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore


def _test_runtime(tmp_path: Path):
    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path}/test.db",
        object_root=tmp_path / "store",
        lease_seconds=30,
    )
    database = Database(settings.database_url)
    database.create_schema()
    store = LocalObjectStore(settings.object_root)
    return settings, database, store


def test_deletion_removes_shared_object(tmp_path: Path):
    settings, database, store = _test_runtime(tmp_path)
    service = DocumentService(database, store, settings)
    tenant, admin_token = service.bootstrap()
    principal = service.authenticate(admin_token)
    assert principal is not None

    data = b"%PDF-1.7\n1 0 obj"

    doc1, job1, _ = service.submit(
        principal, data, filename="test1.pdf", idempotency_key="idemp_1111"
    )
    doc2, job2, _ = service.submit(
        principal, data, filename="test2.pdf", idempotency_key="idemp_2222"
    )

    assert doc1.source_object_key == doc2.source_object_key
    shared_key = doc1.source_object_key
    assert store.exists(shared_key)

    deleted = service.delete_document(principal, doc1.id)
    assert deleted is True

    # Shared key should still exist
    assert store.exists(shared_key)

    # Delete second doc
    deleted2 = service.delete_document(principal, doc2.id)
    assert deleted2 is True

    # Now it should be gone
    assert not store.exists(shared_key)


def test_purge_removes_shared_object(tmp_path: Path):
    settings, database, store = _test_runtime(tmp_path)
    service = DocumentService(database, store, settings)
    tenant, admin_token = service.bootstrap()
    principal = service.authenticate(admin_token)
    assert principal is not None

    data = b"%PDF-1.7\n1 0 obj"

    doc1, _, _ = service.submit(principal, data, filename="test1.pdf", idempotency_key="idemp_1111")
    doc2, _, _ = service.submit(principal, data, filename="test2.pdf", idempotency_key="idemp_2222")

    assert doc1.source_object_key == doc2.source_object_key
    shared_key = doc1.source_object_key
    assert store.exists(shared_key)

    with database.session() as session:
        d1 = session.get(StoredDocument, doc1.id)
        assert d1 is not None
        d1.delete_after = utcnow() - timedelta(days=1)
        session.commit()

    purged = service.purge_expired()
    assert purged == 1

    # Should still exist
    assert store.exists(shared_key)

    with database.session() as session:
        d2 = session.get(StoredDocument, doc2.id)
        assert d2 is not None
        d2.delete_after = utcnow() - timedelta(days=1)
        session.commit()

    purged2 = service.purge_expired()
    assert purged2 == 1

    # Should not exist
    assert not store.exists(shared_key)
