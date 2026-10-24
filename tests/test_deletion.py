from datetime import timedelta
from pathlib import Path

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database, utcnow
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore


def test_document_deletion_preserves_shared_objects(tmp_path: Path) -> None:
    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path / 'service.db'}",
        object_root=tmp_path / "objects",
        bootstrap_token="bootstrap-test-token",
    )
    database = Database(settings.database_url)
    database.create_schema()
    store = LocalObjectStore(settings.object_root)
    service = DocumentService(database, store, settings)

    _tenant, admin_token = service.bootstrap()
    principal = service.authenticate(admin_token)
    assert principal is not None

    # Submit first document
    doc1, _, _ = service.submit(
        principal, b"%PDF-1.7\ntestcontent", filename="doc1.pdf", idempotency_key=None
    )

    # Submit second document with the SAME content
    doc2, _, _ = service.submit(
        principal, b"%PDF-1.7\ntestcontent", filename="doc2.pdf", idempotency_key=None
    )

    # Check that they share the same object key
    assert doc1.source_object_key == doc2.source_object_key
    shared_key = doc1.source_object_key

    # Check object exists
    assert store.exists(shared_key)

    # Delete first document
    assert service.delete_document(principal, doc1.id) is True

    # The object should STILL exist because doc2 references it
    assert store.exists(shared_key)

    # Delete second document
    assert service.delete_document(principal, doc2.id) is True

    # NOW the object should be deleted
    assert not store.exists(shared_key)


def test_purge_expired_preserves_shared_objects(tmp_path: Path) -> None:
    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path / 'service.db'}",
        object_root=tmp_path / "objects",
        bootstrap_token="bootstrap-test-token",
    )
    database = Database(settings.database_url)
    database.create_schema()
    store = LocalObjectStore(settings.object_root)
    service = DocumentService(database, store, settings)

    _tenant, admin_token = service.bootstrap()
    principal = service.authenticate(admin_token)
    assert principal is not None

    # Submit first document
    doc1, _, _ = service.submit(
        principal, b"%PDF-1.7\npurgecontent", filename="doc1.pdf", idempotency_key=None
    )

    # Submit second document with the SAME content
    doc2, _, _ = service.submit(
        principal, b"%PDF-1.7\npurgecontent", filename="doc2.pdf", idempotency_key=None
    )

    shared_key = doc1.source_object_key
    assert store.exists(shared_key)

    # Manually set doc1 to be expired
    with database.session() as session:
        from dzdoc_service.db import StoredDocument

        db_doc1 = session.get(StoredDocument, doc1.id)
        db_doc1.delete_after = utcnow() - timedelta(days=1)
        session.commit()

    # Run purge
    purged_count = service.purge_expired()
    assert purged_count == 1

    # The object should STILL exist because doc2 references it
    assert store.exists(shared_key)

    # Expire doc2
    with database.session() as session:
        from dzdoc_service.db import StoredDocument

        db_doc2 = session.get(StoredDocument, doc2.id)
        db_doc2.delete_after = utcnow() - timedelta(days=1)
        session.commit()

    purged_count2 = service.purge_expired()
    assert purged_count2 == 1

    # NOW the object should be deleted
    assert not store.exists(shared_key)
