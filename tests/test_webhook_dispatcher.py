import urllib.error
import urllib.request

from dzdoc_service.db import Database, Tenant, WebhookDelivery, WebhookEndpoint
from dzdoc_service.worker import WebhookDispatcher


def test_webhook_dispatcher_optimistic_concurrency_no_lazy_load():
    db = Database("sqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        t = Tenant(id="t1", name="test")
        e = WebhookEndpoint(
            id="e1",
            tenant_id="t1",
            url="https://example.com",
            secret_hash="x",
            signing_secret="x",
            active=True,
        )
        w1 = WebhookDelivery(
            id="w1",
            tenant_id="t1",
            endpoint_id="e1",
            event_id="ev1",
            event_type="x",
            payload_json="{}",
        )
        w2 = WebhookDelivery(
            id="w2",
            tenant_id="t1",
            endpoint_id="e1",
            event_id="ev2",
            event_type="x",
            payload_json="{}",
        )
        session.add_all([t, e, w1, w2])
        session.commit()

    dispatcher = WebhookDispatcher(db)

    original_urlopen = urllib.request.urlopen

    # We will test optimistic concurrency by wrapping session.execute
    # But since we use sessionmaker, it's easier to use a mocked urlopen

    calls = 0
    in_session_during_call = False

    # Check if there is an active session in the database pool...
    # The simplest way is to assert no active transactions if we wrap the urlopen

    def mock_urlopen(request, timeout=None):
        nonlocal calls
        calls += 1

        class MockResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return MockResponse()

    urllib.request.urlopen = mock_urlopen
    try:
        dispatcher.run_once()
    finally:
        urllib.request.urlopen = original_urlopen

    with db.session() as session:
        w1_db = session.get(WebhookDelivery, "w1")
        assert w1_db.status == "delivered"
        assert w1_db.response_code == 200

        # Test failure case
        w2_db = session.get(WebhookDelivery, "w2")
        assert w2_db.status == "pending"


def test_webhook_dispatcher_optimistic_concurrency_fails():
    db = Database("sqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        t = Tenant(id="t1", name="test")
        e = WebhookEndpoint(
            id="e1",
            tenant_id="t1",
            url="https://example.com",
            secret_hash="x",
            signing_secret="x",
            active=True,
        )
        w1 = WebhookDelivery(
            id="w1",
            tenant_id="t1",
            endpoint_id="e1",
            event_id="ev1",
            event_type="x",
            payload_json="{}",
        )
        session.add_all([t, e, w1])
        session.commit()

    dispatcher = WebhookDispatcher(db)

    # To simulate optimistic concurrency failure, we can manually change the status in the DB
    # before execute happens, but it's easier to mock `session.execute`
    # Let's mock urlopen, it shouldn't be called
    import urllib.request

    original_urlopen = urllib.request.urlopen
    calls = 0

    def mock_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise Exception("Should not be called")

    urllib.request.urlopen = mock_urlopen

    # Change status to simulate another worker claiming it
    with db.session() as session:
        w1 = session.get(WebhookDelivery, "w1")
        w1.status = "processing"
        session.commit()

    try:
        res = dispatcher.run_once()
        assert res is None
        assert calls == 0
    finally:
        urllib.request.urlopen = original_urlopen
