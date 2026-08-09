"""Service process entry points."""

from __future__ import annotations

import argparse
import time

import uvicorn

from .api import create_app
from .config import ServiceSettings
from .db import Database
from .service import DocumentService, ServiceError
from .storage import ObjectStore, build_object_store
from .worker import WebhookDispatcher, Worker


def _runtime() -> tuple[ServiceSettings, Database, ObjectStore]:
    settings = ServiceSettings.from_env()
    database = Database(settings.database_url)
    database.create_schema()
    return settings, database, build_object_store(settings)


def api_main() -> None:
    settings = ServiceSettings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        proxy_headers=settings.environment == "production",
    )


def worker_main() -> None:
    parser = argparse.ArgumentParser(description="Run a DzDoc processing worker")
    parser.add_argument("--capability", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    settings, database, store = _runtime()
    worker = Worker(database, store, settings, capability=args.capability)
    webhooks = WebhookDispatcher(database)
    service = DocumentService(database, store, settings)
    next_purge = 0.0
    while True:
        processed = worker.run_once()
        webhooks.run_once()
        if time.monotonic() >= next_purge:
            service.purge_expired()
            next_purge = time.monotonic() + 3600
        if args.once:
            return
        if processed is None:
            time.sleep(max(0.1, args.poll_seconds))


def bootstrap_main() -> None:
    _settings, database, store = _runtime()
    service = DocumentService(database, store, _settings)
    try:
        tenant_id, token = service.bootstrap()
    except ServiceError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"tenant_id={tenant_id}")
    print(f"api_key={token}")
