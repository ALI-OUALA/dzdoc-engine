import pytest
from datetime import timedelta
from dzdoc_service.db import Database, Job, Tenant, StoredDocument, claim_job, utcnow, new_id

def test_claim_job_stealing(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/test.db")
    db.create_schema()

    with db.session() as session:
        tenant = Tenant(id="t1", name="t1")
        doc1 = StoredDocument(id="d1", tenant_id="t1", sha256="1", source_name="1", media_kind="pdf", size_bytes=1, source_object_key="1")
        doc2 = StoredDocument(id="d2", tenant_id="t1", sha256="2", source_name="2", media_kind="pdf", size_bytes=1, source_object_key="2")
        job1 = Job(id="j1", tenant_id="t1", document_id="d1", capability="cpu", status="queued", attempt_count=0)
        job2 = Job(id="j2", tenant_id="t1", document_id="d2", capability="cpu", status="queued", attempt_count=0)
        session.add_all([tenant, doc1, doc2, job1, job2])
        session.commit()

    with db.session() as session_b:
        from sqlalchemy import select, and_, or_
        current = utcnow()

        # Worker B gets candidates
        candidates_b = session_b.execute(
            select(Job.id, Job.status, Job.attempt_count, Job.started_at)
            .where(
                Job.capability == "cpu",
                Job.attempt_count < Job.max_attempts,
                Job.available_at <= current,
                or_(
                    Job.status == "queued",
                    and_(Job.status == "processing", Job.lease_expires_at < current),
                ),
            )
            .order_by(Job.priority.desc(), Job.created_at)
            .limit(8)
        ).all()

        # Before Worker B loops, Worker A claims Job 1 and Job 2!
        with db.session() as session_a:
            claimed_a1 = claim_job(session_a, capability="cpu", lease_seconds=100)
            claimed_a2 = claim_job(session_a, capability="cpu", lease_seconds=100)
            assert claimed_a1.id == "j1"
            assert claimed_a2.id == "j2"
            session_a.commit()

        # Let's simulate the loop in claim_job for Worker B:
        from sqlalchemy import update
        import secrets
        claimed_b = None
        for job_id, previous_status, attempt_count, started_at in candidates_b:
            token = secrets.token_hex(24)
            result = session_b.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == previous_status,
                    Job.attempt_count == attempt_count,
                )
                .values(
                    status="processing",
                    attempt_count=attempt_count + 1,
                    lease_token=token,
                    lease_expires_at=current + timedelta(seconds=100),
                    started_at=started_at or current,
                )
            )
            if getattr(result, "rowcount", 0) == 1:
                session_b.commit()
                claimed_b = session_b.get(Job, job_id)
                break
            session_b.rollback()

        assert claimed_b is None, f"Worker B stole job {claimed_b.id}!"
