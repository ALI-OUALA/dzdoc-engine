"""Typer command line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .exporters import export_document, export_prediction
from .ingestion import IngestionError, SecureIngestor
from .native_pdf import PdfInspectionError
from .pipeline import FakePipeline

app = typer.Typer(help="Arabic-French document intelligence foundation.")


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
            inspection = FakePipeline().pdf_inspector.inspect(document)
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
    except (IngestionError, PdfInspectionError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def process(source: Path, output: Path | None = typer.Option(None, "--output", "-o")) -> None:
    """Run native-first deterministic foundation pipeline."""

    try:
        document = FakePipeline().process_path(source)
    except (IngestionError, PdfInspectionError) as exc:
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
) -> None:
    """Write a public DZ-Bench-shaped prediction artifact."""

    try:
        document = FakePipeline().process_path(source)
        export_prediction(
            document,
            output,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            manifest_checksum=manifest_checksum,
        )
    except (IngestionError, PdfInspectionError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(output))
