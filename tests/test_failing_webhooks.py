from pathlib import Path

from sqlalchemy import select

from dzdoc.models import Document
from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database, Job, WebhookDelivery, WebhookEndpoint, new_id
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore
from dzdoc_service.worker import Worker


class FailingPipeline:
    def process_bytes(self, data: bytes, *, name: str) -> Document:
        raise ValueError("Simulated processing error")


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


def test_failed_job_triggers_failed_webhook(tmp_path: Path):
    settings, database, store = _runtime(tmp_path)
    service = DocumentService(database, store, settings)
    tenant_id, token = service.bootstrap()
    principal = service.authenticate(token)
    assert principal is not None

    with database.session() as session:
        endpoint = WebhookEndpoint(
            id=new_id(),
            tenant_id=tenant_id,
            url="https://example.com/webhook",
            secret_hash="hash",
            signing_secret="secret",
        )
        session.add(endpoint)
        session.commit()

    document, job, _ = service.submit(
        principal, b"%PDF-1.7\n", filename="test.pdf", idempotency_key="abcdefghij"
    )

    with database.session() as session:
        job_db = session.get(Job, job.id)
        assert job_db is not None
        job_db.max_attempts = 1
        session.commit()

    worker = Worker(database, store, settings, pipeline=FailingPipeline())
    worker.run_once()

    with database.session() as session:
        deliveries = session.scalars(
            select(WebhookDelivery).where(WebhookDelivery.tenant_id == tenant_id)
        ).all()
        assert len(deliveries) == 1
        delivery = deliveries[0]
        assert delivery.event_type == "document.failed"
        import json

        payload = json.loads(delivery.payload_json)
        assert payload["status"] == "failed"
