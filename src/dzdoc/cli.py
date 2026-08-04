"""Typer command line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .benchmark import BundleError, PublicBundleRunner
from .exporters import export_document, export_prediction
from .ingestion import IngestionError, SecureIngestor
from .native_pdf import PdfInspectionError
from .ocr import OcrDependencyError, PaddleOcrEngine
from .pipeline import HybridPipeline

app = typer.Typer(help="Arabic-French document intelligence foundation.")


@app.command("evaluate-bundle")
def evaluate_bundle_command(
    manifest: Path = typer.Option(..., exists=True, readable=True),
    records: Path = typer.Option(..., exists=True, readable=True),
    assets_dir: Path = typer.Option(..., exists=True, file_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
    recognition_mode: str = typer.Option("routed", "--recognition-mode"),
    model_dir: Path | None = typer.Option(
        None,
        "--model-dir",
        exists=True,
        file_okay=False,
        help="Directory containing the reviewed OCR assets; defaults to DZDOC_MODEL_DIR.",
    ),
) -> None:
    """Process a public DZ-Bench raster bundle without importing DZ-Bench."""

    try:
        pipeline = HybridPipeline(
            ocr=PaddleOcrEngine(model_root=model_dir, recognition_mode=recognition_mode)
        )
        PublicBundleRunner(pipeline).run(manifest, records, assets_dir, output)
    except (BundleError, IngestionError, OcrDependencyError, PdfInspectionError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(output))


@app.command()
def inspect(source: Path) -> None:
    """Inspect local signature, checksum, and native PDF pages."""

    try:
        document = SecureIngestor().load(source)
        payload: dict[str, object] = {
            "name": document.name,
            "kind": document.kind,
            "size_bytes": document.size_bytes,
            "sha256": document.sha256,
        }
        if document.kind == "pdf":
            inspection = HybridPipeline().pdf_inspector.inspect(document)
            payload["page_count"] = inspection.page_count
            payload["pages"] = [
                {
                    "page_index": page.page_index,
                    "width": page.width,
                    "height": page.height,
                    "route": page.quality.route,
                    "reason": page.quality.reason,
                }
                for page in inspection.pages
            ]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    except (IngestionError, OcrDependencyError, PdfInspectionError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def process(
    source: Path,
    output: Path | None = typer.Option(None, "--output", "-o"),
    model_dir: Path | None = typer.Option(
        None,
        "--model-dir",
        exists=True,
        file_okay=False,
        help="Directory containing the reviewed OCR assets; defaults to DZDOC_MODEL_DIR.",
    ),
) -> None:
    """Run native-first deterministic foundation pipeline."""

    try:
        document = _pipeline(model_dir=model_dir).process_path(source)
    except (IngestionError, OcrDependencyError, PdfInspectionError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output:
        export_document(document, output)
        typer.echo(str(output))
    else:
        typer.echo(document.model_dump_json(indent=2))


@app.command("export-prediction")
def export_prediction_command(
    source: Path,
    dataset_id: str = typer.Option(..., "--dataset-id"),
    dataset_revision: str = typer.Option(..., "--dataset-revision"),
    output: Path = typer.Option(..., "--output", "-o"),
    manifest_checksum: str | None = typer.Option(None, "--manifest-checksum"),
    model_dir: Path | None = typer.Option(
        None,
        "--model-dir",
        exists=True,
        file_okay=False,
        help="Directory containing the reviewed OCR assets; defaults to DZDOC_MODEL_DIR.",
    ),
) -> None:
    """Write a public DZ-Bench-shaped prediction artifact."""

    try:
        document = _pipeline(model_dir=model_dir).process_path(source)
        export_prediction(
            document,
            output,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            manifest_checksum=manifest_checksum,
        )
    except (IngestionError, OcrDependencyError, PdfInspectionError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(output))


def _pipeline(*, model_dir: Path | None = None) -> HybridPipeline:
    if model_dir is None:
        return HybridPipeline()
    return HybridPipeline(ocr=PaddleOcrEngine(model_root=model_dir))
