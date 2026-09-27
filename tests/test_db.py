from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dzdoc_service.db import Base, Job, StoredDocument, Tenant, claim_job


def test_claim_job_optimistic_concurrency_no_lazy_load():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    session = Session()
    t = Tenant(id="t1", name="test")
    d = StoredDocument(
        id="d1",
        tenant_id="t1",
        sha256="xxx",
        source_name="x",
        media_kind="pdf",
        size_bytes=10,
        source_object_key="x",
    )
    session.add(t)
    session.add(d)

    # We create two jobs to claim
    j1 = Job(id="j1", tenant_id="t1", document_id="d1", status="queued")
    j2 = Job(id="j2", tenant_id="t1", document_id="d1", status="queued")
    session.add_all([j1, j2])
    session.commit()

    # Normally claim_job will try to claim j1 first.
    # To test that session.rollback() doesn't evict the remaining candidates
    # (since they are just scalars), we can try to intercept or we can simulate
    # the scenario that fails in ORM objects.
    # We will simulate exactly the situation by replacing the session.execute temporarily.

    original_execute = session.execute

    execute_calls = 0

    def mock_execute(*args, **kwargs):
        nonlocal execute_calls
        execute_calls += 1
        # The first call is the select statement
        if execute_calls == 2:
            # Second call is the update statement for the first candidate.
            # We mock rowcount=0 to trigger rollback
            class MockResult:
                rowcount = 0

            return MockResult()
        return original_execute(*args, **kwargs)

    session.execute = mock_execute

    claimed = claim_job(session, capability="cpu", lease_seconds=60)

    assert claimed is not None
    assert claimed.id == "j2"
    assert claimed.status == "processing"
    assert claimed.lease_token is not None

from dzdoc_service.db import WebhookEndpoint, WebhookDelivery, claim_delivery

def test_claim_delivery_optimistic_concurrency_no_lazy_load():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    session = Session()
    t = Tenant(id="t1", name="test")
    e = WebhookEndpoint(id="e1", tenant_id="t1", url="http://example.com", secret_hash="x", signing_secret="x")
    session.add(t)
    session.add(e)

    # We create two deliveries to claim
    d1 = WebhookDelivery(id="d1", tenant_id="t1", endpoint_id="e1", event_id="ev1", event_type="t", payload_json="{}", status="pending")
    d2 = WebhookDelivery(id="d2", tenant_id="t1", endpoint_id="e1", event_id="ev2", event_type="t", payload_json="{}", status="pending")
    session.add_all([d1, d2])
    session.commit()

    original_execute = session.execute

    execute_calls = 0

    def mock_execute(*args, **kwargs):
        nonlocal execute_calls
        execute_calls += 1
        if execute_calls == 2:
            class MockResult:
                rowcount = 0
            return MockResult()
        return original_execute(*args, **kwargs)

    session.execute = mock_execute

    claimed = claim_delivery(session, lease_seconds=60)

    assert claimed is not None
    assert claimed.id == "d2"
    assert claimed.status == "processing"
    assert claimed.attempt_count == 1
