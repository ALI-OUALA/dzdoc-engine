from sqlalchemy import event

from dzdoc_service.db import Database, Job, StoredDocument, Tenant, claim_job


def test_claim_job_no_lazy_loads_after_rollback():
    """
    Test that claim_job correctly fetches scalar properties to avoid
    lazy-loads when optimistic concurrency fails on a candidate and
    the session is rolled back.
    """
    db = Database("sqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        session.add(Tenant(id="tenant-1", name="Test"))
        session.add(
            StoredDocument(
                id="doc-1",
                tenant_id="tenant-1",
                sha256="abc",
                source_name="doc.pdf",
                media_kind="pdf",
                size_bytes=100,
                source_object_key="key",
            )
        )
        session.add(
            StoredDocument(
                id="doc-2",
                tenant_id="tenant-1",
                sha256="def",
                source_name="doc.pdf",
                media_kind="pdf",
                size_bytes=100,
                source_object_key="key",
            )
        )
        session.add(
            Job(
                id="job-1",
                tenant_id="tenant-1",
                document_id="doc-1",
                capability="cpu",
                status="queued",
                attempt_count=0,
            )
        )
        session.add(
            Job(
                id="job-2",
                tenant_id="tenant-1",
                document_id="doc-2",
                capability="cpu",
                status="queued",
                attempt_count=0,
            )
        )
        session.commit()

    with db.session() as session:
        # We patch session.execute to simulate an optimistic concurrency
        # failure on job-1, which will trigger a session.rollback()
        original_execute = session.execute

        def mock_execute(stmt, *args, **kwargs):
            if hasattr(stmt, "is_update") and getattr(stmt, "is_update", False):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                if "job-1" in compiled:

                    class MockResult:
                        rowcount = 0

                    return MockResult()
            return original_execute(stmt, *args, **kwargs)

        session.execute = mock_execute

        # Count queries to ensure no unexpected lazy loads happen
        query_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        event.listen(db.engine, "before_cursor_execute", before_cursor_execute)

        job = claim_job(session, capability="cpu", lease_seconds=60)

        event.remove(db.engine, "before_cursor_execute", before_cursor_execute)

        assert job is not None
        assert job.id == "job-2"
        # 1. SELECT candidates
        # 2. UPDATE job-2 (job-1 is mocked)
        # 3. SELECT job-2 (session.get at the end)
        assert query_count == 3
