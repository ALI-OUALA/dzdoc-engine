from __future__ import annotations

from dzdoc_service.db import Database, Job, claim_job


def test_claim_job_handles_optimistic_concurrency_and_rollbacks(tmp_path) -> None:
    db = Database("sqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        jobs = [
            Job(id=f"job-{i}", tenant_id="tenant", document_id=f"doc-{i}", status="queued")
            for i in range(5)
        ]
        session.add_all(jobs)
        session.commit()

    with db.session() as session:
        # We will mock session.execute to simulate a concurrent failure on the first candidate.
        # When the first candidate tries to update, we return 0 rowcount (meaning it was updated
        # by another worker). We also simulate the second candidate being deleted concurrently
        # to ensure that `session.rollback()` doesn't cause ObjectDeletedError when the loop
        # moves on to evaluate it.
        real_execute = session.execute
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            stmt = str(args[0])
            if "UPDATE jobs" in stmt and call_count == 0:
                call_count += 1
                # Simulate a concurrent worker deleting the second candidate while we fail
                # to claim the first candidate.
                with db.engine.connect() as conn:
                    conn.exec_driver_sql("DELETE FROM jobs WHERE id = 'job-1'")
                    conn.commit()

                # Return a result with rowcount=0 to trigger `session.rollback()`
                class FakeResult:
                    rowcount = 0

                return FakeResult()
            return real_execute(*args, **kwargs)

        session.execute = side_effect  # type: ignore

        # The first candidate (job-0) will fail the UPDATE check.
        # The loop will rollback the session.
        # The second candidate (job-1) will fail the UPDATE check (because it was deleted).
        # The loop will rollback the session again.
        # The third candidate (job-2) should succeed.
        job = claim_job(session, capability="cpu", lease_seconds=60)

        assert job is not None
        assert job.id == "job-2"
        assert call_count == 1
