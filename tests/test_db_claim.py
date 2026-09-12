import pytest
from datetime import datetime
from dzdoc_service.db import Database, Base, Tenant, Job, new_id, claim_job

def test_claim_job_handles_concurrency_race():
    db = Database("sqlite://")
    Base.metadata.create_all(db.engine)
    with db.session() as session:
        t = Tenant(id=new_id(), name="t")
        session.add(t)
        j1 = Job(id=new_id(), tenant_id=t.id, document_id=new_id(), capability="cpu")
        j2 = Job(id=new_id(), tenant_id=t.id, document_id=new_id(), capability="cpu")
        j3 = Job(id=new_id(), tenant_id=t.id, document_id=new_id(), capability="cpu")
        session.add_all([j1, j2, j3])
        session.commit()

        # By default, sqlite will return them in insertion order: j1, j2, j3
        # We want j1 to fail (simulate claimed by someone else),
        # j2 to fail because it was deleted by someone else,
        # and j3 to succeed.

        j2_id = j2.id
        j3_id = j3.id

        orig_execute = session.execute
        update_calls = 0

        def fake_execute(stmt, *args, **kwargs):
            nonlocal update_calls
            if hasattr(stmt, "is_update") and stmt.is_update:
                update_calls += 1
                if update_calls == 1:
                    # For the first candidate (j1), simulate a concurrent delete of j2
                    # and fail the update for j1.
                    with db.engine.connect() as conn:
                        conn.execute(Job.__table__.delete().where(Job.id == j2_id))
                        conn.commit()
                    class FakeResult:
                        rowcount = 0
                    return FakeResult()
            return orig_execute(stmt, *args, **kwargs)

        session.execute = fake_execute

        # With the old code, this would raise ObjectDeletedError when accessing j2.attempt_count
        job = claim_job(session, capability="cpu", lease_seconds=60)
        assert job is not None
        assert job.id == j3_id

if __name__ == "__main__":
    pytest.main(["-v", __file__])
