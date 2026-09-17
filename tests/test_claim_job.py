from dzdoc_service.db import Database, Job, StoredDocument, Tenant, claim_job, new_id


def test_claim_job_rollback_lazy_load():
    db = Database("sqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        t = Tenant(id=new_id(), name="test")
        doc = StoredDocument(
            id=new_id(),
            tenant_id=t.id,
            sha256="0" * 64,
            source_name="x",
            media_kind="pdf",
            size_bytes=10,
            source_object_key="a",
        )
        j1 = Job(id=new_id(), tenant_id=t.id, document_id=doc.id, priority=10, status="queued")
        j2 = Job(id=new_id(), tenant_id=t.id, document_id=doc.id, priority=5, status="queued")
        session.add_all([t, doc, j1, j2])
        session.commit()

        j2_id = j2.id

    with db.session() as session:
        original_execute = session.execute

        def mock_execute(statement, *args, **kwargs):
            if getattr(statement, "is_update", False):
                # The parameters are in args[0] usually for an execute
                # Or we can just fail the first update
                class MockResult:
                    rowcount = 0

                # Check if it's the update for j1. We can just use a counter or global
                if mock_execute.call_count == 0:
                    mock_execute.call_count += 1
                    return MockResult()
            return original_execute(statement, *args, **kwargs)

        mock_execute.call_count = 0
        session.execute = mock_execute

        claimed = claim_job(session, capability="cpu", lease_seconds=60)
        assert claimed is not None
        assert claimed.id == j2_id
