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
        "DZDOC_EMBEDDED_WORKER",
        "DZDOC_ENVIRONMENT",
    ):
        monkeypatch.delenv(name, raising=False)
    value = ServiceSettings.from_env()
    assert value.database_url == "sqlite:///./.data/dzdoc.db"
    assert value.max_upload_bytes == 50 * 1024 * 1024
    assert value.embedded_worker is False
    monkeypatch.setenv("DZDOC_EMBEDDED_WORKER", "true")
    assert ServiceSettings.from_env().embedded_worker is True


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


def test_webhook_dispatcher_captures_http_error_codes(tmp_path: Path, monkeypatch) -> None:
    import urllib.error
    import urllib.request

    from dzdoc_service.db import WebhookDelivery, WebhookEndpoint, new_id, safe_json
    from dzdoc_service.worker import WebhookDispatcher

    settings, database, store = _runtime(tmp_path)

    with database.session() as session:
        tenant_id = new_id()
        endpoint = WebhookEndpoint(
            id=new_id(),
            tenant_id=tenant_id,
            url="https://example.com/webhook",
            secret_hash="hash",
            signing_secret="secret",
        )
        delivery = WebhookDelivery(
            id=new_id(),
            tenant_id=tenant_id,
            endpoint_id=endpoint.id,
            event_id=new_id(),
            event_type="test",
            payload_json=safe_json({"test": 1}),
        )
        session.add(endpoint)
        session.add(delivery)
        session.commit()
        delivery_id = delivery.id

    class MockHTTPError(urllib.error.HTTPError):
        def __init__(self, url, code, msg, hdrs, fp):
            super().__init__(url, code, msg, hdrs, fp)  # type: ignore

    def mock_urlopen(request, timeout=None):
        raise MockHTTPError(request.full_url, 400, "Bad Request", {}, None)  # type: ignore

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    dispatcher = WebhookDispatcher(database)
    dispatcher.run_once()

    with database.session() as session:
        updated = session.get(WebhookDelivery, delivery_id)
        assert updated is not None
        assert updated.response_code == 400
        assert updated.last_error == "MockHTTPError"
        assert updated.status == "pending"  # Still retries
        assert updated.attempt_count == 1


def test_claim_job_concurrent_rollback_prevents_lazy_load(tmp_path: Path) -> None:
    settings, database, store = _runtime(tmp_path)

    from dzdoc_service.db import Job, StoredDocument, Tenant, claim_job

    # Create required rows for a job
    with database.session() as session:
        tenant = Tenant(id="t1", name="test")
        doc1 = StoredDocument(
            id="d1",
            tenant_id="t1",
            sha256="abc",
            source_name="x",
            media_kind="pdf",
            size_bytes=100,
            source_object_key="key",
        )
        doc2 = StoredDocument(
            id="d2",
            tenant_id="t1",
            sha256="def",
            source_name="y",
            media_kind="pdf",
            size_bytes=100,
            source_object_key="key2",
        )
        session.add_all([tenant, doc1, doc2])
        session.commit()

    with database.session() as session:
        session.add(
            Job(id="j1", tenant_id="t1", document_id="d1", capability="cpu", attempt_count=0)
        )
        session.add(
            Job(id="j2", tenant_id="t1", document_id="d2", capability="cpu", attempt_count=0)
        )
        session.commit()

    with database.session() as session:
        # We simulate a concurrent claim by locking the first job out
        # Using a mock for `session.execute` causes typing issues, so we'll instead
        # run a parallel session that actually updates the attempt_count, causing
        # the optimistic concurrency check in claim_job to fail on the first try.
        # However, SQLite in-memory might have locking issues with concurrent updates,
        # but SQLAlchemy sessions on the same engine should be fine as long as we don't
        # hold conflicting locks. Actually, the easiest way to mock optimistic failure
        # without typing errors is to monkeypatch `session.execute` correctly or patch `update`?

        # To fail the optimistic update without type errors, we just use another session to change
        # the row before `claim_job` updates it. But we don't have a hook inside `claim_job` loop.
        # Instead, let's use the mock, but ignore type errors or cast properly.
        from typing import Any

        from sqlalchemy.sql import Update

        original_execute = session.execute

        call_count = 0

        def fake_execute(statement: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            if (
                isinstance(statement, Update)
                and getattr(statement, "table", None) is not None
                and getattr(statement.table, "name", "") == "jobs"
            ):
                call_count += 1
                if call_count == 1:
                    # Simulate that the first job was already claimed
                    class EmptyResult:
                        rowcount = 0

                    return EmptyResult()
            return original_execute(statement, *args, **kwargs)  # type: ignore

        session.execute = fake_execute  # type: ignore

        claimed = claim_job(session, capability="cpu", lease_seconds=60)

        assert claimed is not None
        assert claimed.id == "j2"
        assert claimed.status == "processing"
