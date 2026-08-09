# ADR 0003: guarded PaddleOCR-VL fallback

Status: accepted and CPU-smoke-qualified (2026-08-09).

## Decision

Keep deterministic native/Paddle OCR as the default. Escalate at most one region per
page only for low confidence, ambiguous candidates, or digit disagreement. A fallback
cannot replace deterministic evidence unless its schema/length/control checks pass, its
logical numbers agree when deterministic candidates agree, and its candidate score gains
at least 0.08. Failure preserves the deterministic result.

The first adapter is PaddleOCR-VL-1.6, Apache-2.0, pinned to Hugging Face revision
`c5630abae1d940eafe0697512a0325494b02ab42`. It is the smallest reviewed current
document parser with explicit multilingual Arabic support and an official 1B profile.
DeepSeek-OCR-2 (3B, 6.32 GiB) and Qwen3-VL-4B-Instruct (8.28 GiB) exceed this CPU-first
fallback envelope. Granite Docling 258M has attractive size but insufficient confirmed
Arabic evidence for this role.

PaddleOCR-VL output confidence is not calibrated. When absent, the adapter records a
conservative 0.82 heuristic; DZ-Bench confidence metrics must expose this limitation.
Every attempt records trigger, status, model/revision, latency, prompt label, decoding,
and bounded raw output. The adapter accepts only explicit local assets and never uploads
documents or downloads models implicitly.

## Evidence boundary

Official model metadata and vendor OmniDocBench results informed candidate selection;
they are not DzDoc quality claims. A pinned local CPU run restored the difficult mixed
TTC region exactly in 87.736 seconds including cold model load. In a one-page DZ-Bench
run capped at one escalation, CER improved from 0.6831 to 0.6093 while runtime increased
from 15.67 to 87.89 seconds; field F1 stayed 0.9474. This supports guarded use, not broad
VLM use. The fallback remains disabled by default.
