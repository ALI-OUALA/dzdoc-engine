1. **Move blocking HTTP request outside SQLAlchemy session context** in `WebhookDispatcher.run_once` (`src/dzdoc_service/worker.py`).
    - Currently, `urllib.request.urlopen` executes inside a `with self.database.session() as session:` block. This holds a database connection open while waiting for external I/O, which can exhaust the DB connection pool if webhooks are slow.
    - Change it to fetch the `WebhookDelivery` data, extend its `available_at` by `timeout_seconds + 5` (as a lease), and commit the session.
    - Perform the HTTP request outside the session context.
    - Open a new session to update the delivery status, attempt count, and next `available_at`.
2. **Add/improve test** in `tests/test_service.py` to ensure webhooks process correctly without the DB session blocking issue. (The existing test `test_webhook_dispatcher_captures_http_error_codes` will be verified to pass, and can be augmented to check connection pool safety or mock state if necessary, but just verifying existing behavior works with the new flow is good enough).
3. **Run checks** (`pytest`, `ruff`, `pyright`).
4. **Complete pre commit steps** to make sure proper testing, verifications, reviews and reflections are done.
5. **Submit the change** with a descriptive commit message explaining the problem and fix.
