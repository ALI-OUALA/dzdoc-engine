import json
from pathlib import Path

from sqlalchemy import select

from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import (
    Database,
    Job,
    StoredDocument,
    Tenant,
    WebhookDelivery,
    WebhookEndpoint,
    new_id,
)
from dzdoc_service.storage import LocalObjectStore
from dzdoc_service.worker import Worker


def test_failed_webhooks(tmp_path: Path):
    db = Database("sqlite:///:memory:")
    db.create_schema()
    store = LocalObjectStore(tmp_path / "obj")
    settings = ServiceSettings(
        database_url="sqlite:///:memory:", object_root=tmp_path / "obj", max_attempts=3
    )

    with db.session() as session:
        t = Tenant(id=new_id(), name="t")
        session.add(t)
        doc = StoredDocument(
            id=new_id(),
            tenant_id=t.id,
            sha256="0",
            source_name="x",
            media_kind="pdf",
            size_bytes=10,
            source_object_key="a",
        )
        # Setup job on its final attempt
        job = Job(
            id=new_id(),
            tenant_id=t.id,
            document_id=doc.id,
            max_attempts=3,
            attempt_count=2,  # Will become 3 after claim, causing permanent failure
            status="queued",
        )
        endpoint = WebhookEndpoint(
            id=new_id(), tenant_id=t.id, url="http://local", secret_hash="x", signing_secret="x"
        )
        session.add_all([doc, job, endpoint])
        session.commit()
        job_id = job.id
        doc_id = doc.id

    class FailingPipeline:
        def process_bytes(self, data, name):
            raise ValueError("Processing permanently failed")

    worker = Worker(db, store, settings, pipeline=FailingPipeline())
    # This run will fail and queue a document.failed webhook
    worker.run_once()

    with db.session() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "dead_letter"

        deliveries = session.scalars(select(WebhookDelivery)).all()
        assert len(deliveries) == 1

        delivery = deliveries[0]
        assert delivery.event_type == "document.failed"

        payload = json.loads(delivery.payload_json)
        assert payload["type"] == "document.failed"
        assert payload["status"] == "failed"
        assert payload["job_id"] == job_id
        assert payload["document_id"] == doc_id
