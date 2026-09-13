from dzdoc_service.db import Database, Job, Tenant, claim_job, new_id


def test_claim_job_rollback_prevents_lazy_load_exceptions():
    """
    Test that when claim_job encounters a concurrent update and calls session.rollback(),
    it doesn't trigger a lazy-load on the ORM object in the next iteration of the loop,
    which would otherwise raise a MissingGreenlet exception or result in DetachedInstanceError
    if the session state was lost (or simply perform an unintended query).

    By fetching scalar columns (Job.id, Job.status, etc) instead of the whole Job object,
    the loop variables are plain Python types and detached from the ORM session state,
    so rolling back the session doesn't expire them.
    """
    database = Database("sqlite://")
    database.create_schema()

    with database.session() as session:
        tenant_id = new_id()
        session.add(Tenant(id=tenant_id, name="Test"))
        session.commit()

        j1 = Job(
            id=new_id(), tenant_id=tenant_id, document_id="doc1", status="queued", capability="cpu"
        )
        j2 = Job(
            id=new_id(), tenant_id=tenant_id, document_id="doc2", status="queued", capability="cpu"
        )
        session.add_all([j1, j2])
        session.commit()

    with database.session() as session:
        original_execute = session.execute
        call_count = 0

        def fake_execute(statement, *args, **kwargs):
            nonlocal call_count
            if getattr(statement, "is_dml", False):
                call_count += 1
                if call_count == 1:

                    class FakeResult:
                        rowcount = 0

                    return FakeResult()
            return original_execute(statement, *args, **kwargs)

        session.execute = fake_execute

        from sqlalchemy import event

        select_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal select_count
            if statement.strip().lower().startswith("select"):
                select_count += 1

        event.listen(session.bind, "before_cursor_execute", before_cursor_execute)

        claimed = claim_job(session, capability="cpu", lease_seconds=60)

        event.remove(session.bind, "before_cursor_execute", before_cursor_execute)

        assert claimed is not None
        assert claimed.document_id == j2.document_id

        # 1 select for initial candidate list, 1 select for final session.get()
        # If there were lazy loads triggered on candidate.status / candidate.attempt_count
        # during the second loop iteration, it would be > 2.
        assert select_count == 2
