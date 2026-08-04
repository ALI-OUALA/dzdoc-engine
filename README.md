# DzDoc Engine

Independent source-available foundation for Arabic–French document intelligence.

Current Phase 1 foundation provides:

- versioned canonical document models with raw, normalized, and search text;
- safe local document ingestion and SHA-256 fingerprinting;
- optional PyMuPDF native PDF inspection and a native-text quality gate;
- explicit hybrid-pipeline protocols with no vendor imports in core models;
- deterministic fake pipeline that records when OCR is required;
- JSON export and a neutral DZ-Bench `Predictions` artifact.

No production OCR model is bundled. Empty OCR pages are reported as explicit
`ocr_required` warnings; they are not silent success claims.

## Quick start

```powershell
uv run dzdoc inspect .\document.pdf
uv run dzdoc process .\document.pdf --output .\document.json
uv run dzdoc export-prediction .\document.pdf --dataset-id synthetic-smoke --dataset-revision 0.1.0 --output .\predictions.json
```

Install PDF inspection support with `uv sync --extra pdf`. The local environment
used for development already provides PyMuPDF, but it remains an optional adapter.

Prediction JSON follows the public `Predictions` contract implemented independently
by `dz-bench`; this package does not import `dz_bench`.

## Status

Implemented and tested: Phase 1 structural foundation, safe ingestion checks, native
text quality routing, JSON serialization, CLI smoke flow, and contract-shaped export.

Not implemented: production OCR recognizers, layout detection, rendering adapters,
VLM fallback, API/workers, and benchmark accuracy claims.
