"""Application service: tenancy, idempotent submission, review, retention."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from dzdoc.ingestion import IngestionError, SecureIngestor

from .config import ServiceSettings
from .db import (
    ApiKey,
    Correction,
    Database,
    Job,
    StoredDocument,
    Tenant,
    UsageRecord,
    WebhookEndpoint,
    new_id,
    utcnow,
)
from .security import generate_api_key, hash_secret, verify_secret
from .storage import ObjectStore

ALL_SCOPES = {
    "documents:read",
    "documents:write",
    "documents:review",
    "documents:delete",
    "keys:manage",
    "webhooks:manage",
    "usage:read",
}


class ServiceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Principal:
    tenant_id: str
    key_id: str
    scopes: frozenset[str]

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise PermissionError(f"missing scope: {scope}")


class DocumentService:
    def __init__(self, database: Database, store: ObjectStore, settings: ServiceSettings) -> None:
        self.database = database
        self.store = store
        self.settings = settings
        self.ingestor = SecureIngestor(max_bytes=settings.max_upload_bytes)

    def bootstrap(self, name: str = "Default tenant") -> tuple[str, str]:
        with self.database.session() as session:
            tenant = session.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))
            if tenant is None:
                tenant = Tenant(id=new_id(), name=name, retention_days=self.settings.retention_days)
                session.add(tenant)
                session.commit()
            existing = session.scalar(select(ApiKey).where(ApiKey.tenant_id == tenant.id).limit(1))
            if existing is not None:
                raise ServiceError(
                    "tenant already has an API key; refusing to reveal or replace it"
                )
            token, prefix, secret_hash = generate_api_key()
            session.add(
                ApiKey(
                    id=new_id(),
                    tenant_id=tenant.id,
                    name="bootstrap",
                    prefix=prefix,
                    secret_hash=secret_hash,
                    scopes_json=json.dumps(sorted(ALL_SCOPES)),
                )
            )
            session.commit()
            return tenant.id, token

    def authenticate(self, token: str) -> Principal | None:
        if not token.startswith("dz_live_") or "." not in token:
            return None
        prefix = token.removeprefix("dz_live_").split(".", 1)[0]
        with self.database.session() as session:
            key = session.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
            if (
                key is None
                or key.revoked_at is not None
                or not verify_secret(token, key.secret_hash)
            ):
                return None
            tenant = session.get(Tenant, key.tenant_id)
            if tenant is None or not tenant.active:
                return None
            key.last_used_at = utcnow()
            session.commit()
            return Principal(key.tenant_id, key.id, frozenset(key.scopes))

    def create_key(self, principal: Principal, *, name: str, scopes: set[str]) -> str:
        principal.require("keys:manage")
        if not scopes or not scopes <= ALL_SCOPES:
            raise ServiceError("API key scopes are invalid")
        token, prefix, secret_hash = generate_api_key()
        with self.database.session() as session:
            session.add(
                ApiKey(
                    id=new_id(),
                    tenant_id=principal.tenant_id,
                    name=name[:120],
                    prefix=prefix,
                    secret_hash=secret_hash,
                    scopes_json=json.dumps(sorted(scopes)),
                )
            )
            session.commit()
        return token

    def submit(
        self,
        principal: Principal,
        data: bytes,
        *,
        filename: str,
        idempotency_key: str | None,
        capability: str = "cpu",
    ) -> tuple[StoredDocument, Job, bool]:
        principal.require("documents:write")
        if capability not in {"cpu", "gpu"}:
            raise ServiceError("capability must be cpu or gpu")
        if idempotency_key is not None and not 8 <= len(idempotency_key) <= 200:
            raise ServiceError("Idempotency-Key must contain 8 to 200 characters")
        try:
            document_input = self.ingestor.from_bytes(data, name=filename)
        except IngestionError as exc:
            raise ServiceError(str(exc)) from exc
        with self.database.session() as session:
            if idempotency_key:
                existing = session.scalar(
                    select(Job).where(
                        Job.tenant_id == principal.tenant_id,
                        Job.idempotency_key == idempotency_key,
                    )
                )
                if existing:
                    document = session.get(StoredDocument, existing.document_id)
                    assert document is not None
                    return document, existing, False
            object_key = self.store.put(document_input.data)
            tenant = session.get(Tenant, principal.tenant_id)
            assert tenant is not None
            document = StoredDocument(
                id=new_id(),
                tenant_id=principal.tenant_id,
                sha256=document_input.sha256,
                source_name=document_input.name,
                media_kind=document_input.kind,
                size_bytes=document_input.size_bytes,
                source_object_key=object_key,
                delete_after=utcnow() + timedelta(days=tenant.retention_days),
            )
            job = Job(
                id=new_id(),
                tenant_id=principal.tenant_id,
                document_id=document.id,
                idempotency_key=idempotency_key,
                capability=capability,
                max_attempts=self.settings.max_attempts,
            )
            session.add_all([document, job])
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                if not idempotency_key:
                    raise
                existing = session.scalar(
                    select(Job).where(
                        Job.tenant_id == principal.tenant_id,
                        Job.idempotency_key == idempotency_key,
                    )
                )
                if existing is None:
                    raise ServiceError("idempotent submission conflict") from exc
                current = session.get(StoredDocument, existing.document_id)
                assert current is not None
                return current, existing, False
            return document, job, True

    def list_jobs(self, principal: Principal, limit: int = 50) -> list[Job]:
        principal.require("documents:read")
        with self.database.session() as session:
            return list(
                session.scalars(
                    select(Job)
                    .where(Job.tenant_id == principal.tenant_id)
                    .order_by(Job.created_at.desc())
                    .limit(min(max(limit, 1), 200))
                )
            )

    def get_job(self, principal: Principal, job_id: str) -> Job | None:
        principal.require("documents:read")
        with self.database.session() as session:
            return session.scalar(
                select(Job).where(Job.id == job_id, Job.tenant_id == principal.tenant_id)
            )

    def get_document(self, principal: Principal, document_id: str) -> StoredDocument | None:
        principal.require("documents:read")
        with self.database.session() as session:
            return session.scalar(
                select(StoredDocument).where(
                    StoredDocument.id == document_id,
                    StoredDocument.tenant_id == principal.tenant_id,
                    StoredDocument.deleted_at.is_(None),
                )
            )

    def result(self, principal: Principal, document_id: str) -> bytes | None:
        document = self.get_document(principal, document_id)
        if document is None or document.result_object_key is None:
            return None
        return self.store.get(document.result_object_key)

    def correct(
        self,
        principal: Principal,
        document_id: str,
        *,
        target_id: str,
        previous_text: str,
        corrected_text: str,
        reason: str | None,
    ) -> Correction:
        principal.require("documents:review")
        if not corrected_text.strip() or len(corrected_text) > 20_000:
            raise ServiceError("corrected text is empty or too long")
        with self.database.session() as session:
            document = session.scalar(
                select(StoredDocument).where(
                    StoredDocument.id == document_id,
                    StoredDocument.tenant_id == principal.tenant_id,
                    StoredDocument.deleted_at.is_(None),
                )
            )
            if document is None:
                raise ServiceError("document not found")
        correction = Correction(
            id=new_id(),
            tenant_id=principal.tenant_id,
            document_id=document_id,
            target_id=target_id[:200],
            previous_text=previous_text,
            corrected_text=corrected_text,
            actor_key_id=principal.key_id,
            reason=reason[:300] if reason else None,
        )
        with self.database.session() as session:
            session.add(correction)
            session.commit()
        return correction

    def delete_document(self, principal: Principal, document_id: str) -> bool:
        principal.require("documents:delete")
        with self.database.session() as session:
            document = session.scalar(
                select(StoredDocument).where(
                    StoredDocument.id == document_id,
                    StoredDocument.tenant_id == principal.tenant_id,
                )
            )
            if document is None:
                return False
            self.store.delete(document.source_object_key)
            if document.result_object_key:
                self.store.delete(document.result_object_key)
            document.deleted_at = utcnow()
            document.status = "deleted"
            session.commit()
            return True

    def purge_expired(self, *, now=None) -> int:
        current = now or utcnow()
        count = 0
        with self.database.session() as session:
            documents = session.scalars(
                select(StoredDocument).where(
                    StoredDocument.deleted_at.is_(None),
                    StoredDocument.delete_after.is_not(None),
                    StoredDocument.delete_after <= current,
                )
            ).all()
            for document in documents:
                self.store.delete(document.source_object_key)
                if document.result_object_key:
                    self.store.delete(document.result_object_key)
                document.deleted_at = current
                document.status = "deleted"
                count += 1
            session.commit()
        return count

    def usage(self, principal: Principal) -> dict[str, int]:
        principal.require("usage:read")
        with self.database.session() as session:
            pages, duration, vlm, jobs = session.execute(
                select(
                    func.coalesce(func.sum(UsageRecord.pages), 0),
                    func.coalesce(func.sum(UsageRecord.duration_ms), 0),
                    func.coalesce(func.sum(UsageRecord.vlm_regions), 0),
                    func.count(UsageRecord.id),
                ).where(UsageRecord.tenant_id == principal.tenant_id)
            ).one()
            return {
                "documents": int(jobs),
                "pages": int(pages),
                "duration_ms": int(duration),
                "vlm_regions": int(vlm),
            }

    def add_webhook(self, principal: Principal, url: str) -> tuple[WebhookEndpoint, str]:
        principal.require("webhooks:manage")
        if not url.startswith("https://") and not (
            self.settings.environment != "production" and url.startswith("http://127.0.0.1")
        ):
            raise ServiceError("webhook URL must use HTTPS")
        secret = "whsec_" + secrets.token_urlsafe(32)
        endpoint = WebhookEndpoint(
            id=new_id(),
            tenant_id=principal.tenant_id,
            url=url,
            secret_hash=hash_secret(secret),
            signing_secret=secret,
        )
        with self.database.session() as session:
            session.add(endpoint)
            session.commit()
        return endpoint, secret
