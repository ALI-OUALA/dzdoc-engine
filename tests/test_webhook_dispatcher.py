import threading
import time
import urllib.error
import urllib.request
from unittest.mock import MagicMock

from dzdoc_service.db import Database, WebhookDelivery, WebhookEndpoint
from dzdoc_service.worker import WebhookDispatcher


def test_webhook_dispatcher_optimistic_concurrency(tmp_path):
    db_path = tmp_path / "test.sqlite"
    db = Database(f"sqlite:///{db_path}")
    db.create_schema()

    with db.session() as session:
        session.add(
            WebhookEndpoint(
                id="ep_1",
                tenant_id="t_1",
                url="http://example.com",
                secret_hash="sh",
                signing_secret="ss",
                active=True,
            )
        )
        session.add(
            WebhookDelivery(
                id="del_1",
                tenant_id="t_1",
                endpoint_id="ep_1",
                event_id="ev_1",
                event_type="test",
                payload_json="{}",
            )
        )
        session.add(
            WebhookDelivery(
                id="del_2",
                tenant_id="t_1",
                endpoint_id="ep_1",
                event_id="ev_2",
                event_type="test",
                payload_json="{}",
            )
        )
        session.commit()

    dispatcher = WebhookDispatcher(db)

    orig_urlopen = urllib.request.urlopen

    def mock_urlopen_slow(*args, **kwargs):
        time.sleep(0.1)
        mock = MagicMock()
        mock.status = 200
        mock.__enter__.return_value = mock
        return mock

    try:
        urllib.request.urlopen = mock_urlopen_slow

        def run_worker():
            dispatcher.run_once()

        t1 = threading.Thread(target=run_worker)
        t2 = threading.Thread(target=run_worker)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

    finally:
        urllib.request.urlopen = orig_urlopen

    with db.session() as session:
        deliveries = session.query(WebhookDelivery).all()
        statuses = [(d.id, d.status) for d in deliveries]

        assert ("del_1", "delivered") in statuses
        assert ("del_2", "delivered") in statuses


def test_webhook_dispatcher_fails_correctly(tmp_path):
    db_path = tmp_path / "test.sqlite"
    db = Database(f"sqlite:///{db_path}")
    db.create_schema()

    with db.session() as session:
        session.add(
            WebhookEndpoint(
                id="ep_1",
                tenant_id="t_1",
                url="http://example.com",
                secret_hash="sh",
                signing_secret="ss",
                active=True,
            )
        )
        session.add(
            WebhookDelivery(
                id="del_1",
                tenant_id="t_1",
                endpoint_id="ep_1",
                event_id="ev_1",
                event_type="test",
                payload_json="{}",
            )
        )
        session.commit()

    dispatcher = WebhookDispatcher(db)

    orig_urlopen = urllib.request.urlopen

    def mock_urlopen_fail(*args, **kwargs):
        raise urllib.error.URLError("Failed")

    try:
        urllib.request.urlopen = mock_urlopen_fail
        dispatcher.run_once()
    finally:
        urllib.request.urlopen = orig_urlopen

    with db.session() as session:
        delivery = session.get(WebhookDelivery, "del_1")
        assert delivery is not None
        assert delivery.status == "pending"
        assert delivery.attempt_count == 1
        assert delivery.last_error == "URLError"


def test_webhook_dispatcher_dead_letter(tmp_path):
    db_path = tmp_path / "test.sqlite"
    db = Database(f"sqlite:///{db_path}")
    db.create_schema()

    with db.session() as session:
        session.add(
            WebhookEndpoint(
                id="ep_1",
                tenant_id="t_1",
                url="http://example.com",
                secret_hash="sh",
                signing_secret="ss",
                active=True,
            )
        )
        session.add(
            WebhookDelivery(
                id="del_1",
                tenant_id="t_1",
                endpoint_id="ep_1",
                event_id="ev_1",
                event_type="test",
                payload_json="{}",
                attempt_count=7,
            )
        )
        session.commit()

    dispatcher = WebhookDispatcher(db)

    orig_urlopen = urllib.request.urlopen

    def mock_urlopen_fail(*args, **kwargs):
        raise urllib.error.URLError("Failed")

    try:
        urllib.request.urlopen = mock_urlopen_fail
        dispatcher.run_once()
    finally:
        urllib.request.urlopen = orig_urlopen

    with db.session() as session:
        delivery = session.get(WebhookDelivery, "del_1")
        assert delivery is not None
        assert delivery.status == "dead_letter"
        assert delivery.attempt_count == 8
        assert delivery.last_error == "URLError"


def test_webhook_dispatcher_cancelled(tmp_path):
    db_path = tmp_path / "test.sqlite"
    db = Database(f"sqlite:///{db_path}")
    db.create_schema()

    with db.session() as session:
        session.add(
            WebhookEndpoint(
                id="ep_1",
                tenant_id="t_1",
                url="http://example.com",
                secret_hash="sh",
                signing_secret="ss",
                active=False,
            )
        )
        session.add(
            WebhookDelivery(
                id="del_1",
                tenant_id="t_1",
                endpoint_id="ep_1",
                event_id="ev_1",
                event_type="test",
                payload_json="{}",
            )
        )
        session.commit()

    dispatcher = WebhookDispatcher(db)

    orig_urlopen = urllib.request.urlopen

    try:
        urllib.request.urlopen = MagicMock()
        dispatcher.run_once()
    finally:
        urllib.request.urlopen = orig_urlopen

    with db.session() as session:
        delivery = session.get(WebhookDelivery, "del_1")
        assert delivery is not None
        assert delivery.status == "cancelled"
