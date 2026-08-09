"""Versioned FastAPI surface for hosted and on-premise DzDoc deployments."""

import hmac
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, HttpUrl

from .config import ServiceSettings
from .db import Database, Job, StoredDocument
from .service import DocumentService, Principal, ServiceError
from .storage import ObjectStore, build_object_store


class KeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: set[str]


class CorrectionCreate(BaseModel):
    target_id: str = Field(min_length=1, max_length=200)
    previous_text: str = Field(max_length=20_000)
    corrected_text: str = Field(min_length=1, max_length=20_000)
    reason: str | None = Field(default=None, max_length=300)


class WebhookCreate(BaseModel):
    url: HttpUrl


def _job(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "document_id": job.document_id,
        "status": job.status,
        "capability": job.capability,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "error": (
            {"code": job.error_code, "message": job.error_message} if job.error_code else None
        ),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def _document(document: StoredDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "sha256": document.sha256,
        "source_name": document.source_name,
        "media_kind": document.media_kind,
        "size_bytes": document.size_bytes,
        "status": document.status,
        "delete_after": document.delete_after,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def create_app(
    settings: ServiceSettings | None = None,
    *,
    database: Database | None = None,
    store: ObjectStore | None = None,
) -> FastAPI:
    config = settings or ServiceSettings.from_env()
    db = database or Database(config.database_url)
    objects = store or build_object_store(config)
    service = DocumentService(db, objects, config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.create_schema()
        yield

    app = FastAPI(
        title="DzDoc API",
        version="1.0.0",
        docs_url="/docs" if config.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.database = db
    app.state.store = objects
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allow_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-API-Key"],
    )

    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def permission_error(_request: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    def principal(
        authorization: Annotated[str | None, Header()] = None,
        x_api_key: Annotated[str | None, Header()] = None,
    ) -> Principal:
        token = x_api_key
        if authorization:
            scheme, _, value = authorization.partition(" ")
            if scheme.lower() != "bearer" or not value:
                raise HTTPException(401, "invalid authorization scheme")
            token = value
        authenticated = service.authenticate(token or "")
        if authenticated is None:
            raise HTTPException(401, "invalid API key")
        return authenticated

    @app.get("/healthz", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["system"])
    def ready() -> dict[str, str]:
        try:
            db.create_schema()
        except Exception as exc:
            raise HTTPException(503, "metadata store unavailable") from exc
        return {"status": "ready"}

    @app.post("/v1/bootstrap", status_code=201, tags=["administration"])
    def bootstrap(
        x_bootstrap_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        if not config.bootstrap_token or not hmac.compare_digest(
            x_bootstrap_token or "", config.bootstrap_token
        ):
            raise HTTPException(404, "not found")
        tenant_id, token = service.bootstrap()
        return {"tenant_id": tenant_id, "api_key": token}

    @app.post("/v1/documents", status_code=202, tags=["documents"])
    async def submit_document(
        user: Annotated[Principal, Depends(principal)],
        file: Annotated[UploadFile, File()],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        capability: Annotated[str, Query(pattern="^(cpu|gpu)$")] = "cpu",
    ) -> dict[str, Any]:
        data = await file.read(config.max_upload_bytes + 1)
        if len(data) > config.max_upload_bytes:
            raise HTTPException(413, "upload exceeds configured limit")
        document, job, created = service.submit(
            user,
            data,
            filename=file.filename or "document",
            idempotency_key=idempotency_key,
            capability=capability,
        )
        return {"created": created, "document": _document(document), "job": _job(job)}

    @app.get("/v1/jobs", tags=["documents"])
    def list_jobs(
        user: Annotated[Principal, Depends(principal)],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        return {"items": [_job(value) for value in service.list_jobs(user, limit)]}

    @app.get("/v1/jobs/{job_id}", tags=["documents"])
    def get_job(job_id: str, user: Annotated[Principal, Depends(principal)]):
        value = service.get_job(user, job_id)
        if value is None:
            raise HTTPException(404, "job not found")
        return _job(value)

    @app.get("/v1/documents/{document_id}", tags=["documents"])
    def get_document(document_id: str, user: Annotated[Principal, Depends(principal)]):
        value = service.get_document(user, document_id)
        if value is None:
            raise HTTPException(404, "document not found")
        return _document(value)

    @app.get("/v1/documents/{document_id}/result", tags=["documents"])
    def get_result(document_id: str, user: Annotated[Principal, Depends(principal)]) -> Response:
        value = service.result(user, document_id)
        if value is None:
            raise HTTPException(404, "result not ready")
        return Response(value, media_type="application/json; charset=utf-8")

    @app.post("/v1/documents/{document_id}/corrections", status_code=201, tags=["review"])
    def create_correction(
        document_id: str,
        body: CorrectionCreate,
        user: Annotated[Principal, Depends(principal)],
    ):
        value = service.correct(user, document_id, **body.model_dump())
        return {
            "id": value.id,
            "document_id": value.document_id,
            "target_id": value.target_id,
            "previous_text": value.previous_text,
            "corrected_text": value.corrected_text,
            "reason": value.reason,
            "created_at": value.created_at,
        }

    @app.delete("/v1/documents/{document_id}", status_code=204, tags=["documents"])
    def delete_document(
        document_id: str, user: Annotated[Principal, Depends(principal)]
    ) -> Response:
        if not service.delete_document(user, document_id):
            raise HTTPException(404, "document not found")
        return Response(status_code=204)

    @app.get("/v1/usage", tags=["administration"])
    def usage(user: Annotated[Principal, Depends(principal)]):
        return service.usage(user)

    @app.post("/v1/api-keys", status_code=201, tags=["administration"])
    def create_key(body: KeyCreate, user: Annotated[Principal, Depends(principal)]):
        return {"api_key": service.create_key(user, name=body.name, scopes=body.scopes)}

    @app.post("/v1/webhooks", status_code=201, tags=["administration"])
    def create_webhook(body: WebhookCreate, user: Annotated[Principal, Depends(principal)]):
        endpoint, secret = service.add_webhook(user, str(body.url))
        return {"id": endpoint.id, "url": endpoint.url, "signing_secret": secret}

    return app


app = create_app()
