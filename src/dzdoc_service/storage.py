"""Content-addressed object storage boundaries."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Protocol

from .config import ServiceSettings


class ObjectStore(Protocol):
    def put(self, data: bytes) -> str: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


class LocalObjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        target = self._path(digest)
        if target.exists():
            return digest
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix="dzdoc-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return digest

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def _path(self, key: str) -> Path:
        if len(key) != 64 or any(value not in "0123456789abcdef" for value in key):
            raise ValueError("object key must be a lowercase SHA-256 digest")
        target = (self.root / key[:2] / key[2:4] / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("object key escaped storage root")
        return target


class S3ObjectStore:
    """Optional S3-compatible adapter; boto3 remains outside core dependencies."""

    def __init__(self, bucket: str, *, endpoint_url: str | None = None, prefix: str = "") -> None:
        try:
            import boto3  # pyright: ignore[reportMissingImports] -- optional s3 extra
        except ImportError as exc:
            raise RuntimeError("S3 storage requires dzdoc[s3]") from exc
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", endpoint_url=endpoint_url)

    def _key(self, digest: str) -> str:
        if len(digest) != 64:
            raise ValueError("invalid object digest")
        path = f"{digest[:2]}/{digest[2:4]}/{digest}"
        return f"{self.prefix}/{path}" if self.prefix else path

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self.client.put_object(Bucket=self.bucket, Key=self._key(digest), Body=data)
        return digest

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except self.client.exceptions.ClientError:
            return False


def build_object_store(settings: ServiceSettings) -> ObjectStore:
    if settings.storage_backend == "s3":
        assert settings.s3_bucket is not None
        return S3ObjectStore(
            settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            prefix=settings.s3_prefix,
        )
    return LocalObjectStore(settings.object_root)
