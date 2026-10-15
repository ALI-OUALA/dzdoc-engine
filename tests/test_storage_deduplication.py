import os
import tempfile
from datetime import UTC
from pathlib import Path

import pytest

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore


def _pdf(content=b"test"):
    return b"%PDF-1.4\n" + content + b"\n%%EOF\n"


def test_delete_shared_object():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        settings = ServiceSettings(database_url=f"sqlite:///{db_path}", object_root=Path(tmpdir))

        db = Database(settings.database_url)
        db.create_schema()
        store = LocalObjectStore(tmpdir)
        service = DocumentService(db, store, settings)

        tenant_id, token = service.bootstrap()
        principal = service.authenticate(token)

        data = _pdf(b"same content")

        doc1, _, _ = service.submit(principal, data, filename="doc1.txt", idempotency_key=None)
        doc2, _, _ = service.submit(principal, data, filename="doc2.txt", idempotency_key=None)

        assert doc1.source_object_key == doc2.source_object_key
        assert store.exists(doc1.source_object_key)

        service.delete_document(principal, doc1.id)

        # doc2 still exists in db, its object must be retained
        assert store.exists(doc2.source_object_key)

        # delete doc2, now the object must be removed
        service.delete_document(principal, doc2.id)
        assert not store.exists(doc2.source_object_key)


def test_purge_shared_object():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        settings = ServiceSettings(database_url=f"sqlite:///{db_path}", object_root=Path(tmpdir))

        db = Database(settings.database_url)
        db.create_schema()
        store = LocalObjectStore(tmpdir)
        service = DocumentService(db, store, settings)

        tenant_id, token = service.bootstrap()
        principal = service.authenticate(token)

        data = _pdf(b"same content purge")

        doc1, _, _ = service.submit(principal, data, filename="doc1.txt", idempotency_key=None)
        doc2, _, _ = service.submit(principal, data, filename="doc2.txt", idempotency_key=None)

        assert doc1.source_object_key == doc2.source_object_key
        assert store.exists(doc1.source_object_key)

        # force expiration
        from datetime import datetime, timedelta

        past = datetime.now(UTC) - timedelta(days=1)

        with db.session() as session:
            d1 = session.get(type(doc1), doc1.id)
            d2 = session.get(type(doc2), doc2.id)
            d1.delete_after = past
            session.commit()

        count = service.purge_expired()
        assert count == 1

        # doc2 still exists and is not expired, object must be retained
        assert store.exists(doc2.source_object_key)

        with db.session() as session:
            d2 = session.get(type(doc2), doc2.id)
            d2.delete_after = past
            session.commit()

        count = service.purge_expired()
        assert count == 1
        assert not store.exists(doc2.source_object_key)


if __name__ == "__main__":
    pytest.main(["-v", "test_storage_deduplication.py"])
