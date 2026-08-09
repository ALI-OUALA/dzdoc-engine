# DzDoc Engine

Independent source-available foundation for Arabic–French document intelligence.

Current deterministic foundation provides:

- versioned canonical document models with raw, normalized, and search text;
- safe local document ingestion and SHA-256 fingerprinting;
- optional PDFium native PDF inspection and a native-text quality gate;
- explicit hybrid-pipeline protocols with no vendor imports in core models;
- page-level native-text routing and rendering of rejected pages only;
- one PP-OCRv5 text-detection pass per OCR page;
- Arabic-first region routing to pinned Arabic/Latin PP-OCRv5 recognizers;
- deterministic candidate fusion, digit disagreement warnings, alternatives,
  provenance, confidence, and RTL/LTR geometric reading order;
- JSON export and a neutral DZ-Bench `Predictions` artifact.

No model weight is bundled or downloaded at install/test time.
Native-text PDFs can be inspected and processed without OCR assets. Raster pages
fail closed unless `DZDOC_MODEL_DIR` (or `--model-dir`) points to the reviewed
asset directories; the engine never performs an implicit unpinned download.

## Quick start

```powershell
uv run dzdoc inspect .\document.pdf
uv run dzdoc process .\document.pdf --output .\document.json
uv run dzdoc export-prediction .\document.pdf --dataset-id synthetic-smoke --dataset-revision 0.1.0 --output .\predictions.json
```

Install the complete local CPU profile and fetch immutable reviewed weights:

```powershell
uv sync --extra pdf --extra ocr-paddle --extra dev
uv run python scripts/fetch_models.py --output .models
$env:DZDOC_MODEL_DIR = (Resolve-Path .models)
uv run dzdoc process .\scan.pdf --output .\document.json
```

Foundation gates run without model downloads:

```powershell
uv sync --extra dev --extra pdf
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

For a public DZ-Bench raster bundle, keep the manifest and ground-truth-free asset index
at the published contract version and run:

```powershell
uv run dzdoc evaluate-bundle --manifest .\manifest.json --assets .\assets.json --assets-dir . --output .\predictions.json
```

The runner validates both public artifacts, rejects unknown fields and unsafe paths,
cross-checks each asset against manifest dimensions/checksum, then sends the same verified
bytes to the pipeline. Generator records and ground truth never enter the OCR process.

Prediction JSON follows the public `Predictions` contract implemented independently
by `dz-bench`; this package does not import `dz_bench`.

## Status

Implemented and tested: canonical models, byte/page/pixel ingestion limits, native
text quality routing, selective rendering, real PP-OCRv5 detect-once OCR, specialist
routing/fusion, JSON serialization, CLI flow, and contract-shaped export.

Measured checkpoint and model rationale are in
`docs/decisions/0002-deterministic-ocr-baseline.md`. It is deliberately not a broad
accuracy claim. Semantic layout/table/equation understanding, handwriting, VLM
fallback, table/figure detection, API/workers, and calibrated confidence remain
incomplete; equation/title classification is currently deterministic and heuristic.
