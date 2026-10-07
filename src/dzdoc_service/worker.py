"""Idempotent CPU/GPU worker and signed webhook delivery."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Protocol

from sqlalchemy import select

from dzdoc.document_packs.invoice_dz import InvoiceDzPack
from dzdoc.models import Document
from dzdoc.pipeline import HybridPipeline

from .config import ServiceSettings
from .db import (
    Database,
    Job,
    StoredDocument,
    UsageRecord,
    WebhookDelivery,
    WebhookEndpoint,
    claim_job,
    new_id,
    safe_json,
    utcnow,
)
from .security import webhook_signature
from .storage import ObjectStore

logger = logging.getLogger("dzdoc.worker")


class Pipeline(Protocol):
    def process_bytes(self, data: bytes, *, name: str) -> Document: ...


class Worker:
    def __init__(
        self,
        database: Database,
        store: ObjectStore,
        settings: ServiceSettings,
        *,
        pipeline: Pipeline | None = None,
        capability: str = "cpu",
    ) -> None:
        self.database = database
        self.store = store
        self.settings = settings
        self.pipeline = pipeline or HybridPipeline()
        self.capability = capability

    def run_once(self) -> str | None:
        with self.database.session() as session:
            job = claim_job(
                session,
                capability=self.capability,
                lease_seconds=self.settings.lease_seconds,
            )
        if job is None:
            return None
        self._process(job.id, job.lease_token or "")
        return job.id

    def _process(self, job_id: str, lease_token: str) -> None:
        started = time.perf_counter()
        with self.database.session() as session:
            job = session.get(Job, job_id)
            if job is None or job.lease_token != lease_token or job.status != "processing":
                return
            document = session.get(StoredDocument, job.document_id)
            if document is None or document.deleted_at is not None:
                self._fail(session, job, "document_missing", "source document is unavailable")
                return
            source_key, source_name = document.source_object_key, document.source_name
        try:
            result = self.pipeline.process_bytes(self.store.get(source_key), name=source_name)
            extraction = InvoiceDzPack().extract(result)
            result = result.model_copy(update={"extractions": [extraction]})
            payload = result.model_dump_json(indent=2).encode()
            result_key = self.store.put(payload)
            with self.database.session() as session:
                job = session.get(Job, job_id)
                document = session.get(StoredDocument, job.document_id) if job else None
                if job is None or document is None or job.lease_token != lease_token:
                    return
                now = utcnow()
                job.status = "succeeded"
                job.finished_at = now
                job.lease_token = None
                job.lease_expires_at = None
                document.status = "succeeded"
                document.result_object_key = result_key
                document.updated_at = now
                session.add(
                    UsageRecord(
                        id=new_id(),
                        tenant_id=job.tenant_id,
                        document_id=document.id,
                        pages=len(result.pages),
                        duration_ms=round((time.perf_counter() - started) * 1000),
                        vlm_regions=int(result.metadata.get("vlm_accepted_regions", 0)),
                    )
                )
                self._queue_webhooks(session, job, document)
                session.commit()
        except Exception as exc:
            logger.warning(
                "job_failed",
                extra={"job_id": job_id, "error_type": type(exc).__name__},
            )
            with self.database.session() as session:
                current = session.get(Job, job_id)
                if current and current.lease_token == lease_token:
                    self._fail(session, current, type(exc).__name__, "document processing failed")

    def _fail(self, session, job: Job, code: str, message: str) -> None:
        job.error_code = code[:80]
        job.error_message = message[:300]
        job.lease_token = None
        job.lease_expires_at = None
        document = session.get(StoredDocument, job.document_id)
        if job.attempt_count >= job.max_attempts:
            job.status = "dead_letter"
            job.finished_at = utcnow()
            if document:
                document.status = "failed"
        else:
            job.status = "queued"
            job.available_at = utcnow() + timedelta(seconds=min(300, 2**job.attempt_count))
            if document:
                document.status = "queued"
        session.commit()

    def _queue_webhooks(self, session, job: Job, document: StoredDocument) -> None:
        endpoints = session.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.tenant_id == job.tenant_id,
                WebhookEndpoint.active.is_(True),
            )
        ).all()
        event_id = new_id()
        payload = safe_json(
            {
                "id": event_id,
                "type": "document.completed",
                "document_id": document.id,
                "job_id": job.id,
                "status": "succeeded",
            }
        )
        for endpoint in endpoints:
            session.add(
                WebhookDelivery(
                    id=new_id(),
                    tenant_id=job.tenant_id,
                    endpoint_id=endpoint.id,
                    event_id=event_id,
                    event_type="document.completed",
                    payload_json=payload,
                )
            )


class WebhookDispatcher:
    def __init__(self, database: Database, *, timeout_seconds: float = 10.0) -> None:
        self.database = database
        self.timeout_seconds = timeout_seconds

    def run_once(self) -> str | None:
        from sqlalchemy import update

        with self.database.session() as session:
            candidates = session.execute(
                select(WebhookDelivery.id, WebhookDelivery.attempt_count)
                .where(
                    WebhookDelivery.status == "pending",
                    WebhookDelivery.available_at <= utcnow(),
                )
                .order_by(WebhookDelivery.available_at)
                .limit(4)
            ).all()

            claimed_delivery = None
            for candidate in candidates:
                result = session.execute(
                    update(WebhookDelivery)
                    .where(
                        WebhookDelivery.id == candidate.id,
                        WebhookDelivery.status == "pending",
                        WebhookDelivery.attempt_count == candidate.attempt_count,
                    )
                    .values(
                        attempt_count=candidate.attempt_count + 1,
                        available_at=utcnow() + timedelta(seconds=60),
                    )
                )
                if getattr(result, "rowcount", 0) == 1:
                    session.commit()
                    claimed_delivery = session.get(WebhookDelivery, candidate.id)
                    break
                session.rollback()

            if claimed_delivery is None:
                return None

            endpoint = session.get(WebhookEndpoint, claimed_delivery.endpoint_id)
            if endpoint is None or not endpoint.active:
                claimed_delivery.status = "cancelled"
                session.commit()
                return claimed_delivery.id

            body = claimed_delivery.payload_json.encode()
            event_id = claimed_delivery.event_id
            delivery_id = claimed_delivery.id
            endpoint_url = endpoint.url
            signing_secret = endpoint.signing_secret
            attempt_count = claimed_delivery.attempt_count

        timestamp = int(time.time())
        request = urllib.request.Request(
            endpoint_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "DzDoc-Event-Id": event_id,
                "DzDoc-Timestamp": str(timestamp),
                "DzDoc-Signature": webhook_signature(signing_secret, timestamp, body),
            },
        )

        response_code = None
        last_error = None
        new_status = "delivered"

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_code = response.status
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, urllib.error.HTTPError):
                response_code = exc.code
            last_error = type(exc).__name__
            if attempt_count >= 8:
                new_status = "dead_letter"
            else:
                new_status = "pending"

        with self.database.session() as session:
            delivery = session.get(WebhookDelivery, delivery_id)
            if delivery:
                if response_code is not None:
                    delivery.response_code = response_code
                if last_error is not None:
                    delivery.last_error = last_error
                delivery.status = new_status
                if new_status == "pending":
                    delivery.available_at = utcnow() + timedelta(
                        seconds=min(3600, 2**attempt_count * 5)
                    )
                session.commit()

        return delivery_id
