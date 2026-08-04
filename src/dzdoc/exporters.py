"""Canonical JSON and neutral DZ-Bench prediction projection."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import SCHEMA_VERSION, Document

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def write_json(payload: Any, target: str | Path) -> Path:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def to_prediction(
    document: Document,
    *,
    dataset_id: str,
    dataset_revision: str,
    manifest_checksum: str | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    if _IDENTIFIER.fullmatch(dataset_id) is None:
        raise ValueError("dataset_id must be a public-contract identifier")
    if _REVISION.fullmatch(dataset_revision) is None:
        raise ValueError("dataset_revision must be a public-contract revision")
    now = datetime.now(UTC)
    metadata = document.metadata
    adapter_name = str(metadata.get("ocr_adapter", "dzdoc.native_pdf"))
    adapter_version = str(
        metadata.get(
            "ocr_adapter_version",
            metadata.get("native_pdf_adapter_version", document.pipeline_version),
        )
    )
    dataset: dict[str, Any] = {"dataset_id": dataset_id, "revision": dataset_revision}
    if manifest_checksum is not None:
        if _SHA256.fullmatch(manifest_checksum) is None:
            raise ValueError("manifest_checksum must be a SHA-256 digest")
        dataset["manifest_checksum"] = {"algorithm": "sha256", "value": manifest_checksum}
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_revision": dataset,
        "coordinate_system": document.coordinate_system.model_dump(mode="json"),
        "system": {
            "name": "dzdoc",
            "version": document.pipeline_version,
            "adapter_name": adapter_name,
            "adapter_version": adapter_version,
            "model_name": metadata.get("ocr_model"),
            "model_version": metadata.get("ocr_asset_revisions"),
            "execution_provider": metadata.get("ocr_execution_provider", "cpu"),
            "command": command,
            "git_commit": None,
            "runtime": {
                "native_pages": int(metadata.get("native_pages", 0)),
                "ocr_pages": int(metadata.get("ocr_pages", 0)),
            },
            "hardware": {},
        },
        "run": {
            "run_id": f"{document.document_id}-run",
            "started_at": now.isoformat(),
            "finished_at": now.isoformat(),
            "duration_ms": float(metadata.get("duration_ms", 0.0)),
            "command": command,
            "dependency_lock_hash": None,
        },
        "samples": [
            {
                "document_id": document.document_id,
                "page_id": page.page_id,
                "status": "success",
                "page": page.model_dump(mode="json"),
                "error": None,
                "runtime_ms": 0.0,
            }
            for page in document.pages
        ],
    }


def export_document(document: Document, target: str | Path) -> Path:
    return write_json(document, target)


def export_prediction(
    document: Document,
    target: str | Path,
    *,
    dataset_id: str,
    dataset_revision: str,
    manifest_checksum: str | None = None,
    command: str | None = None,
) -> Path:
    return write_json(
        to_prediction(
            document,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            manifest_checksum=manifest_checksum,
            command=command,
        ),
        target,
    )
