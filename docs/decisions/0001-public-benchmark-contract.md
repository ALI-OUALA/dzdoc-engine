# ADR 0001: file-level benchmark contract

Status: accepted

DzDoc and DZ-Bench communicate through versioned JSON artifacts, not Python
imports or shared private modules. DzDoc emits `schema_version`, dataset revision,
coordinate-system metadata, system/run metadata, and page samples containing
canonical blocks, lines, spans, provenance, confidence, warnings, and checksums.

This keeps the evaluator engine-neutral and lets a future CLI, HTTP worker, or
third-party OCR adapter produce the same prediction contract.
