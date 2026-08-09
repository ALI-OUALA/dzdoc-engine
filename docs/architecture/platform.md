# Platform architecture

The platform preserves one engine and one public canonical model across CLI,
worker, API, and on-premise use.

```text
client / SDK / review UI
          |
       FastAPI
          |
 PostgreSQL metadata + DB lease queue ---- S3-compatible object storage
          |                                      |
     CPU/GPU workers -----------------------------+
          |
 deterministic-first hybrid engine -> guarded optional VLM -> canonical JSON
```

The initial queue is PostgreSQL-backed. Atomic conditional claims, capability
labels, leases, retry limits, dead-letter status, and idempotency make it safe
for a small multi-worker deployment without Redis. A future queue adapter may
replace it without changing the OCR engine or API artifact contract.

Documents are content-addressed and never stored in SQL. API keys are scrypt
hashes and tenant/scopes are checked in the application service. Corrections
append actor, target, old value, new value, reason, and timestamp. Deletion
removes source and result objects before tombstoning metadata. Webhook payloads
are HMAC-SHA256 signed and retry with bounded backoff.

## Deployment profiles

- Local/offline: SQLite + local object directory + one worker.
- One server: Docker Compose, PostgreSQL, private object volume, API, web, CPU workers.
- Accelerated: add GPU workers advertising `gpu`; submission chooses capability.
- Hosted/private cloud: managed PostgreSQL and any S3-compatible store; run OCI
  API/web/worker images behind the operator's TLS ingress.

Render can host the static web interface or a lightweight API demonstration,
but its free profile is not the production OCR compute target. No provider is
embedded in the core. `render.yaml` intentionally provisions only the static
review client; private documents must not be uploaded until it is connected to
an operator-controlled API with TLS and authentication.

## Security boundary and known gaps

Uploads are size and signature checked, names are reduced to basenames, object
keys are strict SHA-256 values, and no customer text enters logs. Production
must terminate TLS, restrict CORS, use private object storage, rotate secrets,
back up PostgreSQL, and run malware/PDF sandboxing at the infrastructure edge.
Before a hosted multi-tenant release, add versioned database migrations,
encrypted-at-rest webhook signing secrets, SSRF-safe DNS/IP webhook validation,
rate limits, and an external penetration test.
