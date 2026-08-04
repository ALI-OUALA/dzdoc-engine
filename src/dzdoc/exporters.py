"""Canonical JSON and neutral DZ-Bench prediction projection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import SCHEMA_VERSION, Document


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
    now = datetime.now(UTC)
    dataset: dict[str, Any] = {"dataset_id": dataset_id, "revision": dataset_revision}
    if manifest_checksum:
        dataset["manifest_checksum"] = {"algorithm": "sha256", "value": manifest_checksum}
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_revision": dataset,
        "coordinate_system": document.coordinate_system.model_dump(mode="json"),
        "system": {
            "name": "dzdoc",
            "version": document.pipeline_version,
            "adapter_name": "dzdoc.fake_pipeline",
            "adapter_version": document.pipeline_version,
            "model_name": None,
            "model_version": None,
            "execution_provider": "cpu",
            "command": command,
            "git_commit": None,
            "runtime": {"ocr_models_loaded": False},
            "hardware": {},
        },
        "run": {
            "run_id": f"{document.document_id}-run",
            "started_at": now.isoformat(),
            "finished_at": now.isoformat(),
            "duration_ms": 0.0,
            "command": command,
            "dependency_lock_hash": None,
        },
        "samples": [
            {
                "document_id": document.document_id,
                "page_id": page.page_id,
                "status": "success",
                "page": page.model_dump(mode="json"),
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
