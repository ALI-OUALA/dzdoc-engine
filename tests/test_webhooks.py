from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from dzdoc.models import Document
from dzdoc_service.config import ServiceSettings
from dzdoc_service.db import Database, WebhookDelivery
from dzdoc_service.service import DocumentService
from dzdoc_service.storage import LocalObjectStore
from dzdoc_service.worker import WebhookDispatcher, Worker


class FailingPipeline:
    def process_bytes(self, data: bytes, *, name: str) -> Document:
        raise RuntimeError("simulated pipeline failure")


def test_webhook_failure_and_dispatcher_lock(tmp_path: Path) -> None:
    settings = ServiceSettings(
        database_url=f"sqlite:///{tmp_path / 'service.db'}",
        object_root=tmp_path / "objects",
        bootstrap_token="bootstrap-test-token",
        max_attempts=1,
    )
    database = Database(settings.database_url)
    database.create_schema()
    store = LocalObjectStore(settings.object_root)
    service = DocumentService(database, store, settings)

    _tenant, token = service.bootstrap()
    principal = service.authenticate(token)
    service.add_webhook(principal, "https://example.com/webhook")

    _document, job, _ = service.submit(
        principal, b"%PDF-1.7\n", filename="test.pdf", idempotency_key=None
    )

    worker = Worker(database, store, settings, pipeline=FailingPipeline())
    worker.run_once()

    with database.session() as session:
        deliveries = session.scalars(select(WebhookDelivery)).all()
        assert len(deliveries) == 1
        assert "failed" in deliveries[0].payload_json

    dispatcher = WebhookDispatcher(database)

    mock_response_context = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response_context.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response_context) as mock_urlopen:
        result = dispatcher.run_once()
        assert result is not None
        mock_urlopen.assert_called_once()

    with database.session() as session:
        deliveries = session.scalars(select(WebhookDelivery)).all()
        assert len(deliveries) == 1
        assert deliveries[0].status == "delivered"
