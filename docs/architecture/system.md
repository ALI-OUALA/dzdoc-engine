# DzDoc Phase 1 architecture

`SecureIngestor` validates local file signatures, size, regular-file status, and
optional root containment before hashing bytes. `NativePdfInspector` is an
optional PyMuPDF adapter. Native text passes through `assess_native_text`, which
checks empty layers, replacement characters, and control-character corruption.

Trusted text becomes canonical page/block/line/span data. Untrusted or missing
text produces an `ocr_required` warning and an empty page result. This is an
explicit boundary: a later OCR adapter can consume the page without changing
canonical schemas or the native-text gate.

All coordinates use pixel units, top-left origin, x-right/y-down. Native Phase 1
uses page-sized evidence boxes because line geometry is not yet extracted.

`export-prediction` writes the independent DZ-Bench `Predictions` shape as JSON.
The engine does not import benchmark code; compatibility is checked by loading
the artifact in DZ-Bench.
