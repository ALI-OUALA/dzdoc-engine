from pathlib import Path

from fastapi.testclient import TestClient

from dzdoc_service.api import create_app
from dzdoc_service.worker import Worker


def _runtime(tmp_path: Path):
    from dzdoc_service.config import ServiceSettings
    from dzdoc_service.db import Database
    from dzdoc_service.storage import LocalObjectStore

    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path / 'service.db'}",
        object_root=tmp_path / "objects",
        bootstrap_token="bootstrap-test-token",
    )
    database = Database(settings.database_url)
    database.create_schema()
    store = LocalObjectStore(settings.object_root)
    return settings, database, store


class FakePipeline:
    def process_bytes(self, data: bytes, *, name: str):
        from dzdoc.models import Checksum, Document, Page, Provenance

        return Document(
            document_id="processed-document",
            source_name=name,
            source_kind="pdf",
            source_checksum=Checksum(value="b" * 64),
            pages=[
                Page(
                    page_id="page-1",
                    page_index=0,
                    checksum=Checksum(value="a" * 64),
                    width=100,
                    height=100,
                    provenance=Provenance(kind="ocr", source="test"),
                )
            ],
        )


def test_dedup_delete(tmp_path: Path):
    settings, database, store = _runtime(tmp_path)
    app = create_app(settings, database=database, store=store)

    with TestClient(app) as client:
        # 1. Bootstrap
        resp = client.post("/v1/bootstrap", headers={"X-Bootstrap-Token": "bootstrap-test-token"})
        assert resp.status_code == 201
        token = resp.json()["api_key"]

        # 2. Upload doc 1
        data1 = b"%PDF-1.4 Hello Deduplication"
        resp1 = client.post(
            "/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("doc1.txt", data1, "application/pdf")},
        )
        assert resp1.status_code == 202
        doc1_id = resp1.json()["document"]["id"]

        # 3. Upload doc 2 with SAME content
        resp2 = client.post(
            "/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("doc2.txt", data1, "application/pdf")},
        )
        assert resp2.status_code == 202
        doc2_id = resp2.json()["document"]["id"]

        # Process them so result keys exist too
        # FakePipeline will produce same results for the same input filename 'doc.txt'
        worker = Worker(database, store, settings, pipeline=FakePipeline())
        worker.run_once()
        worker.run_once()

        # Delete doc 1
        del_resp = client.delete(
            f"/v1/documents/{doc1_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 204

        # Doc 2 is still using the source and result object keys
        from dzdoc_service.db import StoredDocument

        with database.session() as session:
            doc2 = session.get(StoredDocument, doc2_id)
            assert doc2 is not None
            source_key = doc2.source_object_key
            result_key = doc2.result_object_key

        assert store.get(source_key) is not None, "Source key was incorrectly deleted!"
        if result_key:
            assert store.get(result_key) is not None, "Result key was incorrectly deleted!"
