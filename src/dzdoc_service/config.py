"""Typed service configuration with secure defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ServiceSettings:
    database_url: str = "sqlite:///./.data/dzdoc.db"
    object_root: Path = Path(".data/objects")
    storage_backend: str = "local"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_prefix: str = "dzdoc"
    max_upload_bytes: int = 50 * 1024 * 1024
    retention_days: int = 30
    lease_seconds: int = 900
    max_attempts: int = 3
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    public_base_url: str = "http://127.0.0.1:8000"
    bootstrap_token: str | None = None
    environment: str = "development"
    allow_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0 or self.retention_days < 0:
            raise ValueError("upload and retention limits are invalid")
        if self.lease_seconds <= 0 or self.max_attempts <= 0:
            raise ValueError("worker limits must be positive")
        if self.environment == "production" and not self.bootstrap_token:
            raise ValueError("DZDOC_BOOTSTRAP_TOKEN is required in production")
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("storage backend must be local or s3")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("DZDOC_S3_BUCKET is required for S3 storage")

    @classmethod
    def from_env(cls) -> ServiceSettings:
        defaults = cls()
        origins = tuple(
            value.strip()
            for value in os.getenv(
                "DZDOC_ALLOW_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
            ).split(",")
            if value.strip()
        )
        return cls(
            database_url=os.getenv("DZDOC_DATABASE_URL", defaults.database_url),
            object_root=Path(os.getenv("DZDOC_OBJECT_ROOT", str(defaults.object_root))),
            storage_backend=os.getenv("DZDOC_STORAGE_BACKEND", defaults.storage_backend),
            s3_bucket=os.getenv("DZDOC_S3_BUCKET"),
            s3_endpoint_url=os.getenv("DZDOC_S3_ENDPOINT_URL"),
            s3_prefix=os.getenv("DZDOC_S3_PREFIX", defaults.s3_prefix),
            max_upload_bytes=int(os.getenv("DZDOC_MAX_UPLOAD_BYTES", defaults.max_upload_bytes)),
            retention_days=int(os.getenv("DZDOC_RETENTION_DAYS", defaults.retention_days)),
            lease_seconds=int(os.getenv("DZDOC_LEASE_SECONDS", defaults.lease_seconds)),
            max_attempts=int(os.getenv("DZDOC_MAX_ATTEMPTS", defaults.max_attempts)),
            api_host=os.getenv("DZDOC_API_HOST", defaults.api_host),
            api_port=int(os.getenv("PORT", defaults.api_port)),
            public_base_url=os.getenv("DZDOC_PUBLIC_BASE_URL", defaults.public_base_url),
            bootstrap_token=os.getenv("DZDOC_BOOTSTRAP_TOKEN"),
            environment=os.getenv("DZDOC_ENVIRONMENT", defaults.environment),
            allow_origins=origins,
        )
