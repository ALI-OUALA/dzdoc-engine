from datetime import UTC, datetime, timedelta

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database, StoredDocument, new_id
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore


def _runtime(tmp_path):
    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        object_root=tmp_path / "objects",
        bootstrap_token="boot",
    )
    db = Database(settings.database_url)
    db.create_schema()
    store = LocalObjectStore(settings.object_root)
    return settings, db, store


def test_purge_shared_hash(tmp_path):
    settings, db, store = _runtime(tmp_path)

    # Store some distinct data to get distinct SHA256 hashes
    key1 = store.put(b"shared purge data")

    now = datetime.now(UTC)

    with db.session() as session:
        # Document 1 is expired
        doc1 = StoredDocument(
            id=new_id(),
            tenant_id="t1",
            sha256="hash1",
            source_name="f1",
            media_kind="pdf",
            size_bytes=10,
            source_object_key=key1,
            delete_after=now - timedelta(days=1),
            deleted_at=None,
        )
        # Document 2 is NOT expired and uses same source_object_key
        doc2 = StoredDocument(
            id=new_id(),
            tenant_id="t1",
            sha256="hash1",
            source_name="f2",
            media_kind="pdf",
            size_bytes=10,
            source_object_key=key1,
            delete_after=now + timedelta(days=1),
            deleted_at=None,
        )
        session.add_all([doc1, doc2])
        session.commit()

    service = DocumentService(db, store, settings)
    service.purge_expired(now=now)

    # Check if key1 was deleted
    assert store.exists(key1) is True, "Shared object was unexpectedly deleted during purge"

    # Now verify that when doc2 is purged, the object is actually deleted
    with db.session() as session:
        doc2 = session.get(StoredDocument, doc2.id)
        doc2.delete_after = now - timedelta(days=1)
        session.commit()

    service.purge_expired(now=now)
    assert store.exists(key1) is False, "Object should be deleted when no active references remain"


def test_delete_document_shared_hash(tmp_path):
    settings, db, store = _runtime(tmp_path)

    key1 = store.put(b"shared delete data")

    now = datetime.now(UTC)

    service = DocumentService(db, store, settings)
    tenant, admin_token = service.bootstrap()
    admin = service.authenticate(admin_token)

    with db.session() as session:
        doc1 = StoredDocument(
            id=new_id(),
            tenant_id=tenant,
            sha256="hash2",
            source_name="f1",
            media_kind="pdf",
            size_bytes=10,
            source_object_key=key1,
            delete_after=now + timedelta(days=1),
            deleted_at=None,
        )
        doc2 = StoredDocument(
            id=new_id(),
            tenant_id=tenant,
            sha256="hash2",
            source_name="f2",
            media_kind="pdf",
            size_bytes=10,
            source_object_key=key1,
            delete_after=now + timedelta(days=1),
            deleted_at=None,
        )
        session.add_all([doc1, doc2])
        session.commit()
        doc1_id = doc1.id
        doc2_id = doc2.id

    # Delete doc1, key1 should remain since doc2 still references it
    deleted1 = service.delete_document(admin, doc1_id)
    assert deleted1 is True
    assert store.exists(key1) is True, (
        "Shared object was unexpectedly deleted during single document delete"
    )

    # Delete doc2, key1 should now be removed
    service.delete_document(admin, doc2_id)
    assert store.exists(key1) is False, "Object should be deleted when no active references remain"
