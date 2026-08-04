"""Public-file DZ-Bench runner; no dependency on benchmark internals."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .exporters import write_json
from .models import Checksum
from .pipeline import HybridPipeline

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_COORDINATE_SYSTEM = {"unit": "pixel", "origin": "top_left", "x_axis": "right", "y_axis": "down"}


class BundleError(ValueError):
    """Raised when an evaluation bundle violates the public trust boundary."""


class _PeakRss:
    def __init__(self) -> None:
        try:
            import psutil
        except ImportError as exc:
            raise BundleError("psutil is required by the benchmark runner") from exc
        self.process = psutil.Process()
        self.peak = self.process.memory_info().rss
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self.stop.wait(0.05):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.stop.set()
        self.thread.join()


class PublicBundleRunner:
    def __init__(self, pipeline: HybridPipeline | None = None) -> None:
        self.pipeline = pipeline or HybridPipeline()

    def run(
        self,
        manifest_path: str | Path,
        records_path: str | Path,
        assets_dir: str | Path,
        output: str | Path,
    ) -> Path:
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        manifest = _validate_manifest(_load_json(manifest_path))
        by_page = _validate_records(_load_json(records_path))
        manifest_page_ids = {
            page["page_id"] for document in manifest["documents"] for page in document["pages"]
        }
        unknown_records = set(by_page) - manifest_page_ids
        if unknown_records:
            raise BundleError(
                "records contain unknown page IDs: " + ", ".join(sorted(unknown_records))
            )
        try:
            root = Path(assets_dir).resolve(strict=True)
        except OSError as exc:
            raise BundleError(f"asset root is not readable: {exc}") from exc
        if not root.is_dir():
            raise BundleError("asset root must be a directory")
        samples: list[dict[str, Any]] = []
        with _PeakRss() as memory:
            for document in manifest["documents"]:
                for page in document["pages"]:
                    samples.append(self._sample(document["document_id"], page, by_page, root))
        finished_at = datetime.now(UTC)
        duration_ms = (time.perf_counter() - started) * 1000
        ocr = getattr(self.pipeline, "_ocr", None)
        pipeline_metadata = getattr(ocr, "metadata", None)
        model_name = pipeline_metadata.upstream_model if pipeline_metadata else None
        payload = {
            "schema_version": "1.0.0",
            "dataset_revision": manifest["dataset_revision"],
            "coordinate_system": manifest["coordinate_system"],
            "system": {
                "name": "dzdoc",
                "version": self.pipeline.config.pipeline_version,
                "adapter_name": getattr(ocr, "name", "dzdoc.hybrid"),
                "adapter_version": getattr(ocr, "version", self.pipeline.config.pipeline_version),
                "model_name": model_name,
                "model_version": getattr(ocr, "asset_revisions", None),
                "execution_provider": "cpu",
                "runtime": {"python": platform.python_version()},
                "hardware": {
                    "platform": platform.platform(),
                    "logical_cpus": os.cpu_count() or 1,
                },
            },
            "run": {
                "run_id": f"dzdoc-{time.time_ns()}",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_ms": duration_ms,
            },
            "samples": samples,
        }
        payload["system"]["runtime"]["peak_rss_mb"] = round(memory.peak / 1048576, 3)
        return write_json(payload, output)

    def _sample(self, document_id, page, records, root: Path) -> dict[str, Any]:
        started = time.perf_counter()
        record = records.get(page["page_id"])
        relative_path = record.get("image_path") if record else None
        if not relative_path:
            return _failure(document_id, page["page_id"], "missing", "asset record missing")
        try:
            path = _asset_path(root, relative_path)
        except BundleError as exc:
            return _failure(document_id, page["page_id"], "missing", str(exc))
        max_bytes = getattr(getattr(self.pipeline, "config", None), "max_bytes", 50 * 1024 * 1024)
        try:
            if path.stat().st_size > max_bytes:
                return _failure(document_id, page["page_id"], "crashed", "asset exceeds byte limit")
            data = path.read_bytes()
        except OSError:
            return _failure(document_id, page["page_id"], "missing", "asset cannot be read")
        expected = page["checksum"]["value"].lower()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            return _failure(document_id, page["page_id"], "crashed", "asset checksum mismatch")
        try:
            with _PeakRss() as memory:
                source = self.pipeline.ingestor.from_bytes(data, name=path.name)
                if source.kind != "image":
                    return _failure(
                        document_id, page["page_id"], "crashed", "bundle asset is not an image"
                    )
                document = self.pipeline.process_input(source)
            if len(document.pages) != 1:
                return _failure(
                    document_id, page["page_id"], "crashed", "one asset must produce one page"
                )
            if (
                document.pages[0].width != page["width"]
                or document.pages[0].height != page["height"]
            ):
                return _failure(
                    document_id,
                    page["page_id"],
                    "crashed",
                    "asset dimensions do not match the manifest",
                )
            content = document.pages[0].model_copy(
                update={
                    "page_id": page["page_id"],
                    "page_index": page["page_index"],
                    "checksum": Checksum.model_validate(page["checksum"]),
                }
            )
            return {
                "document_id": document_id,
                "page_id": page["page_id"],
                "status": "success",
                "page": content.model_dump(mode="json"),
                "error": None,
                "runtime_ms": (time.perf_counter() - started) * 1000,
                "peak_memory_mb": memory.peak / 1048576,
            }
        except Exception as exc:
            return _failure(
                document_id,
                page["page_id"],
                "crashed",
                f"{type(exc).__name__} during page processing",
            )


def _failure(document_id: str, page_id: str, status: str, message: str) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "page_id": page_id,
        "status": status,
        "page": None,
        "error": {"code": "bundle_asset_error", "message": message, "retryable": False},
    }


def _asset_path(root: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise BundleError("asset path must be a non-empty string")
    if "\x00" in relative_path:
        raise BundleError("asset path contains an invalid character")
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise BundleError("asset path must stay inside the asset root")
    try:
        path = (root / candidate).resolve()
    except (OSError, ValueError) as exc:
        raise BundleError("asset path is invalid") from exc
    if not path.is_relative_to(root) or not path.is_file():
        raise BundleError("asset path is invalid")
    return path


def _validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BundleError("manifest must be an object")
    _keys(
        value,
        {
            "schema_version",
            "dataset_revision",
            "coordinate_system",
            "documents",
            "reference_sources",
            "notes",
        },
        "manifest",
    )
    version = value.get("schema_version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise BundleError("manifest.schema_version must be semantic version text")
    revision = value.get("dataset_revision")
    if not isinstance(revision, dict):
        raise BundleError("manifest.dataset_revision must be an object")
    _keys(
        revision,
        {"dataset_id", "revision"},
        "dataset_revision",
        optional={"manifest_checksum"},
    )
    _identifier(revision.get("dataset_id"), "dataset_revision.dataset_id")
    if not isinstance(revision.get("revision"), str) or not _REVISION.fullmatch(
        revision["revision"]
    ):
        raise BundleError("dataset_revision.revision is invalid")
    if revision.get("manifest_checksum") is not None:
        _checksum(revision["manifest_checksum"], "dataset_revision.manifest_checksum")
    if value.get("coordinate_system") != _COORDINATE_SYSTEM:
        raise BundleError("manifest.coordinate_system is not the public pixel contract")
    if not isinstance(value.get("documents"), list):
        raise BundleError("manifest.documents must be an array")
    if not isinstance(value.get("reference_sources"), list):
        raise BundleError("manifest.reference_sources must be an array")
    if not isinstance(value.get("notes"), list) or not all(
        isinstance(note, str) for note in value["notes"]
    ):
        raise BundleError("manifest.notes must be an array of strings")

    document_ids: set[str] = set()
    page_ids: set[str] = set()
    for document in value["documents"]:
        if not isinstance(document, dict):
            raise BundleError("manifest documents must be objects")
        _keys(
            document,
            {"document_id", "split", "category", "checksum", "source", "pages"},
            "document",
        )
        document_id = _identifier(document.get("document_id"), "document.document_id")
        if document_id in document_ids:
            raise BundleError(f"duplicate document ID: {document_id}")
        document_ids.add(document_id)
        if document.get("split") not in {"dev", "validation", "test-public", "test-private"}:
            raise BundleError(f"invalid split for document {document_id}")
        _identifier(document.get("category"), f"document {document_id}.category")
        _checksum(document.get("checksum"), f"document {document_id}.checksum")
        _validate_source(document.get("source"), f"document {document_id}.source")
        pages = document.get("pages")
        if not isinstance(pages, list) or not pages:
            raise BundleError(f"document {document_id} must contain pages")
        page_indices: set[int] = set()
        for page in pages:
            if not isinstance(page, dict):
                raise BundleError(f"document {document_id} pages must be objects")
            _keys(
                page,
                {"page_id", "page_index", "checksum", "width", "height", "source_kind", "tags"},
                f"page in {document_id}",
            )
            page_id = _identifier(page.get("page_id"), f"document {document_id}.page_id")
            if page_id in page_ids:
                raise BundleError(f"duplicate page ID: {page_id}")
            page_ids.add(page_id)
            _non_negative_int(page.get("page_index"), f"page {page_id}.page_index")
            if page["page_index"] in page_indices:
                raise BundleError(f"duplicate page index in document {document_id}")
            page_indices.add(page["page_index"])
            _checksum(page.get("checksum"), f"page {page_id}.checksum")
            _positive_int(page.get("width"), f"page {page_id}.width")
            _positive_int(page.get("height"), f"page {page_id}.height")
            if page.get("source_kind") not in {
                "native_pdf",
                "scanned_pdf",
                "image",
                "synthetic_record",
                "unknown",
            }:
                raise BundleError(f"invalid source_kind for page {page_id}")
            tags = page.get("tags")
            if not isinstance(tags, list) or not all(_is_identifier(tag) for tag in tags):
                raise BundleError(f"page {page_id}.tags must contain identifiers")
    reference_ids: set[str] = set()
    for source in value["reference_sources"]:
        _validate_reference_source(source)
        reference_id = source["reference_id"]
        if reference_id in reference_ids:
            raise BundleError(f"duplicate reference source ID: {reference_id}")
        reference_ids.add(reference_id)
    return value


def _validate_records(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, list):
        raise BundleError("records must be an array")
    result: dict[str, dict[str, str]] = {}
    for record in value:
        if not isinstance(record, dict):
            raise BundleError("asset records must be objects")
        _keys(record, {"page_id", "image_path"}, "asset record")
        page_id = _identifier(record.get("page_id"), "asset record.page_id")
        if page_id in result:
            raise BundleError(f"duplicate asset record: {page_id}")
        if not isinstance(record.get("image_path"), str) or not record["image_path"].strip():
            raise BundleError(f"asset record {page_id}.image_path must be text")
        result[page_id] = record
    return result


def _validate_source(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise BundleError(f"{label} must be an object")
    _keys(
        value,
        {"kind", "title", "license_status", "redistribution"},
        label,
        optional={"canonical_source_url", "source_organization", "retrieval_date", "notes"},
    )
    if value.get("kind") not in {
        "synthetic",
        "redistributable",
        "reference-only",
        "private-evaluation",
    }:
        raise BundleError(f"{label}.kind is invalid")
    if not isinstance(value.get("title"), str) or not value["title"].strip():
        raise BundleError(f"{label}.title is required")
    if value.get("license_status") not in {"verified", "unverified", "unknown", "not_applicable"}:
        raise BundleError(f"{label}.license_status is invalid")
    if value.get("redistribution") not in {
        "redistributable",
        "reference-only",
        "private-evaluation",
        "synthetic",
    }:
        raise BundleError(f"{label}.redistribution is invalid")
    for field in ("canonical_source_url", "source_organization", "retrieval_date", "notes"):
        _optional_text(value.get(field), f"{label}.{field}")


def _validate_reference_source(value: Any) -> None:
    label = "reference source"
    if not isinstance(value, dict):
        raise BundleError(f"{label} must be an object")
    _keys(
        value,
        {"reference_id", "title", "license_status", "redistribution", "notes"},
        label,
        optional={"canonical_source_url", "source_organization", "retrieval_date"},
    )
    _identifier(value.get("reference_id"), f"{label}.reference_id")
    if not isinstance(value.get("title"), str) or not value["title"].strip():
        raise BundleError(f"{label}.title is required")
    if value.get("license_status") not in {"verified", "unverified", "unknown"}:
        raise BundleError(f"{label}.license_status is invalid")
    if value.get("redistribution") not in {
        "reference-only",
        "redistributable",
        "private-evaluation",
    }:
        raise BundleError(f"{label}.redistribution is invalid")
    if not isinstance(value.get("notes"), str) or not value["notes"].strip():
        raise BundleError(f"{label}.notes is required")
    for field in ("canonical_source_url", "source_organization", "retrieval_date"):
        _optional_text(value.get(field), f"{label}.{field}")


def _keys(
    value: dict[str, Any], required: set[str], label: str, *, optional: set[str] | None = None
) -> None:
    allowed = required | (optional or set())
    missing = required - value.keys()
    if missing:
        raise BundleError(f"{label} is missing: {', '.join(sorted(missing))}")
    unknown = value.keys() - allowed
    if unknown:
        raise BundleError(f"{label} contains unknown fields: {', '.join(sorted(unknown))}")


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _optional_text(value: Any, label: str) -> None:
    if value is not None and not isinstance(value, str):
        raise BundleError(f"{label} must be text or null")


def _identifier(value: Any, label: str) -> str:
    if not _is_identifier(value):
        raise BundleError(f"{label} is invalid")
    return value


def _checksum(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise BundleError(f"{label} must be an object")
    if set(value) - {"algorithm", "value", "size_bytes"}:
        raise BundleError(f"{label} contains unknown fields")
    if value.get("algorithm") != "sha256" or not isinstance(value.get("value"), str):
        raise BundleError(f"{label} must contain a sha256 value")
    if _SHA256.fullmatch(value["value"]) is None:
        raise BundleError(f"{label}.value is not a sha256 digest")
    size = value.get("size_bytes")
    if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
        raise BundleError(f"{label}.size_bytes is invalid")


def _non_negative_int(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BundleError(f"{label} must be a non-negative integer")


def _positive_int(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BundleError(f"{label} must be a positive integer")


def _load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read bundle artifact: {exc}") from exc
