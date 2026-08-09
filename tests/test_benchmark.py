import hashlib
import json

import pytest
from PIL import Image

from dzdoc.benchmark import PublicBundleRunner
from dzdoc.pipeline import HybridPipeline

pytest.importorskip("PIL")
pytest.importorskip("numpy")
pytest.importorskip("psutil")


class EmptyOcr:
    name = "empty-test"
    version = "1"

    def detect(self, image):
        return []


def test_public_bundle_runner_preserves_benchmark_identity(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    image = image_dir / "page.png"
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")
    png = image.read_bytes()
    checksum = hashlib.sha256(png).hexdigest()
    manifest = {
        "schema_version": "1.0.0",
        "dataset_revision": {"dataset_id": "fixture", "revision": "1.0.0"},
        "coordinate_system": {
            "unit": "pixel",
            "origin": "top_left",
            "x_axis": "right",
            "y_axis": "down",
        },
        "documents": [
            {
                "document_id": "doc-1",
                "split": "test-public",
                "category": "synthetic",
                "checksum": {"algorithm": "sha256", "value": checksum},
                "source": {
                    "kind": "synthetic",
                    "title": "test fixture",
                    "license_status": "not_applicable",
                    "redistribution": "synthetic",
                },
                "pages": [
                    {
                        "page_id": "page-1",
                        "page_index": 0,
                        "checksum": {"algorithm": "sha256", "value": checksum},
                        "width": 8,
                        "height": 8,
                        "source_kind": "image",
                        "tags": ["synthetic"],
                    }
                ],
            }
        ],
        "reference_sources": [],
        "notes": [],
    }
    assets = {
        "schema_version": "1.0.0",
        "dataset_revision": manifest["dataset_revision"],
        "assets": [
            {
                "document_id": "doc-1",
                "page_id": "page-1",
                "media_type": "image/png",
                "relative_path": "images/page.png",
                "checksum": {"algorithm": "sha256", "value": checksum},
                "width": 8,
                "height": 8,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    assets_path = tmp_path / "assets.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assets_path.write_text(json.dumps(assets), encoding="utf-8")
    output = tmp_path / "predictions.json"

    PublicBundleRunner(HybridPipeline(ocr=EmptyOcr())).run(
        manifest_path, assets_path, tmp_path, output
    )

    prediction = json.loads(output.read_text(encoding="utf-8"))
    sample = prediction["samples"][0]
    assert sample["status"] == "success"
    assert sample["document_id"] == "doc-1"
    assert sample["page"]["page_id"] == "page-1"
    assert sample["page"]["checksum"]["value"] == checksum
    assert sample["runtime_ms"] >= 0
    assert sample["peak_memory_mb"] > 0

    assets["assets"][0]["media_type"] = "image/jpeg"
    assets_path.write_text(json.dumps(assets), encoding="utf-8")
    PublicBundleRunner(HybridPipeline(ocr=EmptyOcr())).run(
        manifest_path, assets_path, tmp_path, output
    )
    mismatch = json.loads(output.read_text(encoding="utf-8"))["samples"][0]
    assert mismatch["status"] == "crashed"
    assert "media type" in mismatch["error"]["message"]


def test_public_bundle_runner_rejects_path_traversal(tmp_path):
    checksum = "0" * 64
    manifest_path = tmp_path / "manifest.json"
    assets_path = tmp_path / "assets.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "dataset_revision": {"dataset_id": "fixture", "revision": "1.0.0"},
                "coordinate_system": {
                    "unit": "pixel",
                    "origin": "top_left",
                    "x_axis": "right",
                    "y_axis": "down",
                },
                "documents": [
                    {
                        "document_id": "doc-1",
                        "split": "test-public",
                        "category": "synthetic",
                        "checksum": {"algorithm": "sha256", "value": checksum},
                        "source": {
                            "kind": "synthetic",
                            "title": "test fixture",
                            "license_status": "not_applicable",
                            "redistribution": "synthetic",
                        },
                        "pages": [
                            {
                                "page_id": "page-1",
                                "page_index": 0,
                                "checksum": {"algorithm": "sha256", "value": checksum},
                                "width": 1,
                                "height": 1,
                                "source_kind": "image",
                                "tags": ["synthetic"],
                            }
                        ],
                    }
                ],
                "reference_sources": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    assets_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "dataset_revision": {"dataset_id": "fixture", "revision": "1.0.0"},
                "assets": [
                    {
                        "document_id": "doc-1",
                        "page_id": "page-1",
                        "media_type": "image/png",
                        "relative_path": "../outside.png",
                        "checksum": {"algorithm": "sha256", "value": checksum},
                        "width": 1,
                        "height": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out.json"
    PublicBundleRunner(HybridPipeline(ocr=EmptyOcr())).run(
        manifest_path, assets_path, tmp_path, output
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["samples"][0]["status"] == "missing"
    assert "inside" in result["samples"][0]["error"]["message"]
