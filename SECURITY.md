# Security

DzDoc treats documents as hostile and sensitive. The Phase 1 boundary checks
signatures, size, regular-file status, optional root containment, and hashes
bytes without logging document contents. Temporary staging uses a randomized
directory and cleans up on context exit. No network access or shell execution is
performed by the core.

Production work must add page/dimension/time/memory limits, isolated rendering,
retention/deletion controls, upload authentication, and redacted structured logs.
Report security issues privately to the project owner before public disclosure.
