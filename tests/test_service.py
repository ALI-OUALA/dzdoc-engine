from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from dzdoc.models import Checksum, Document, Page, Provenance
from dzdoc_service.api import create_app
from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore
from dzdoc_service.worker import Worker


class FakePipeline:
    def process_bytes(self, data: bytes, *, name: str) -> Document:
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


def test_idempotent_api_submission_worker_result_and_deletion(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    app = create_app(settings, database=database, store=store)

    with TestClient(app) as client:
        boot = client.post("/v1/bootstrap", headers={"X-Bootstrap-Token": "bootstrap-test-token"})
        assert boot.status_code == 201
        token = boot.json()["api_key"]
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "request-0001"}
        first = client.post(
            "/v1/documents",
            headers=headers,
            files={"file": ("../invoice.pdf", b"%PDF-1.7\n", "application/pdf")},
        )
        second = client.post(
            "/v1/documents",
            headers=headers,
            files={"file": ("invoice.pdf", b"%PDF-1.7\n", "application/pdf")},
        )
        assert first.status_code == second.status_code == 202
        assert first.json()["created"] is True
        assert second.json()["created"] is False
        assert first.json()["job"]["id"] == second.json()["job"]["id"]
        document_id = first.json()["document"]["id"]

        worker = Worker(database, store, settings, pipeline=FakePipeline())
        assert worker.run_once() == first.json()["job"]["id"]
        result = client.get(f"/v1/documents/{document_id}/result", headers=headers)
        assert result.status_code == 200
        payload = result.json()
        assert payload["document_id"] == "processed-document"
        assert payload["extractions"][0]["schema_name"] == "invoice-dz"
        assert client.get("/v1/usage", headers=headers).json()["documents"] == 1
        assert client.delete(f"/v1/documents/{document_id}", headers=headers).status_code == 204
        assert client.get(f"/v1/documents/{document_id}", headers=headers).status_code == 404


def test_scopes_isolate_review_and_tenants(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    service = DocumentService(database, store, settings)
    _tenant, admin_token = service.bootstrap()
    admin = service.authenticate(admin_token)
    assert admin is not None
    review_token = service.create_key(admin, name="reviewer", scopes={"documents:review"})
    document, _job, _created = service.submit(
        admin,
        b"%PDF-1.7\n",
        filename="safe.pdf",
        idempotency_key=None,
    )
    reviewer = service.authenticate(review_token)
    assert reviewer is not None
    correction = service.correct(
        reviewer,
        document.id,
        target_id="line-1",
        previous_text="1200",
        corrected_text="1 200,00",
        reason="verified against source",
    )
    assert correction.corrected_text == "1 200,00"
    try:
        service.list_jobs(reviewer)
    except PermissionError as exc:
        assert "documents:read" in str(exc)
    else:
        raise AssertionError("review-only key unexpectedly read jobs")


def test_api_rejects_oversized_and_invalid_uploads(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    settings = ServiceSettings(
        database_url=settings.database_url,
        object_root=settings.object_root,
        max_upload_bytes=8,
        bootstrap_token="bootstrap-test-token",
    )
    app = create_app(settings, database=database, store=store)
    service = DocumentService(database, store, settings)
    _tenant, token = service.bootstrap()
    headers = {"X-API-Key": token}
    with TestClient(app) as client:
        too_large = client.post(
            "/v1/documents",
            headers=headers,
            files={"file": ("x.pdf", b"%PDF-1.7-too-large")},
        )
        invalid = client.post("/v1/documents", headers=headers, files={"file": ("x.txt", b"hello")})
    assert too_large.status_code == 413
    assert invalid.status_code == 422
    assert "signature" in invalid.json()["detail"]


def test_settings_from_environment_uses_real_defaults(monkeypatch) -> None:
    for name in (
        "DZDOC_DATABASE_URL",
        "DZDOC_OBJECT_ROOT",
        "DZDOC_MAX_UPLOAD_BYTES",
        "DZDOC_RETENTION_DAYS",
        "DZDOC_LEASE_SECONDS",
        "DZDOC_MAX_ATTEMPTS",
        "DZDOC_API_HOST",
        "PORT",
        "DZDOC_PUBLIC_BASE_URL",
        "DZDOC_BOOTSTRAP_TOKEN",
        "DZDOC_ENVIRONMENT",
    ):
        monkeypatch.delenv(name, raising=False)
    value = ServiceSettings.from_env()
    assert value.database_url == "sqlite:///./.data/dzdoc.db"
    assert value.max_upload_bytes == 50 * 1024 * 1024


def test_result_is_valid_utf8_json(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)
    service = DocumentService(database, store, settings)
    _, token = service.bootstrap()
    principal = service.authenticate(token)
    assert principal is not None
    _document, job, _ = service.submit(
        principal, b"%PDF-1.7\n", filename="فاتورة.pdf", idempotency_key=None
    )
    Worker(database, store, settings, pipeline=FakePipeline()).run_once()
    stored = service.result(principal, job.document_id)
    assert stored is not None
    assert json.loads(stored.decode("utf-8"))["source_name"] == "فاتورة.pdf"
