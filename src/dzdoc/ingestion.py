"""Hostile-input checks for local documents."""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


class IngestionError(ValueError):
    """Raised when a document fails local trust-boundary checks."""


@dataclass(frozen=True, slots=True)
class DocumentInput:
    name: str
    data: bytes
    kind: str
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def _kind_for_signature(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if data[:3] == b"\xff\xd8\xff":
        return "image"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image"
    if (
        data.startswith((b"GIF87a", b"GIF89a"))
        or data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
    ):
        return "image"
    return None


class SecureIngestor:
    def __init__(self, *, max_bytes: int = 50 * 1024 * 1024, root_dir: Path | None = None) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.max_bytes = max_bytes
        self.root_dir = root_dir.resolve() if root_dir else None

    def from_bytes(self, data: bytes, *, name: str = "document.bin") -> DocumentInput:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise IngestionError("document data must be bytes-like")
        if len(data) > self.max_bytes:
            raise IngestionError(f"document exceeds {self.max_bytes} byte limit")
        data = bytes(data)
        kind = _kind_for_signature(data)
        if kind is None:
            raise IngestionError("unsupported or invalid document signature")
        safe_name = Path(name).name or "document.bin"
        return DocumentInput(name=safe_name[:255], data=data, kind=kind, sha256=_sha256(data))

    def load(self, source: str | Path) -> DocumentInput:
        path = Path(source).expanduser().resolve(strict=True)
        if not path.is_file():
            raise IngestionError("document source is not a regular file")
        if self.root_dir and not path.is_relative_to(self.root_dir):
            raise IngestionError("document source is outside the configured root")
        if path.stat().st_size > self.max_bytes:
            raise IngestionError(f"document exceeds {self.max_bytes} byte limit")
        with path.open("rb") as handle:
            data = handle.read(self.max_bytes + 1)
        return self.from_bytes(data, name=path.name)

    @contextmanager
    def stage(self, document: DocumentInput) -> Iterator[Path]:
        """Stage bytes in a randomized temporary directory and always clean them up."""

        with tempfile.TemporaryDirectory(prefix="dzdoc-") as directory:
            target = Path(directory) / "input.bin"
            target.write_bytes(document.data)
            yield target


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
