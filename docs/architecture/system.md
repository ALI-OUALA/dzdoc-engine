# DzDoc deterministic architecture

`SecureIngestor` validates signature, byte limit, regular-file status, and
optional root containment. The pipeline and PDFium adapter add page-count and
decoded/rendered-pixel limits before model work.

For PDFs, the liberal-licensed PDFium adapter extracts native text first. The
quality gate rejects missing, replacement/control-heavy, implausible, repeated,
or phantom layers. Trusted pages become canonical evidence directly and are not
rendered. Rejected pages alone are rendered at the configured DPI.

OCR pages follow one explicit cascade:

```text
one PP-OCRv5 detection pass
  -> perspective crop each region
  -> Arabic specialist as routing probe
  -> Latin specialist only when uncertain or script-inconsistent
  -> deterministic confidence/script/digit fusion
  -> geometric line bands with RTL/LTR direction
  -> canonical page/block/line/span JSON with alternatives and warnings
```

Core models do not import PaddleOCR, PaddlePaddle, OpenCV, PDFium, or Pillow.
Those libraries remain in adapters and optional dependency profiles. Model
weights are external, immutable-revision assets; install and unit tests never
download them.

All coordinates are pixels with top-left origin and x-right/y-down. Native pages
use render-equivalent dimensions at the configured DPI. Native line geometry is
not yet extracted, so trusted native text currently has one page-sized evidence
box. OCR lines use detector geometry.

`export-prediction` writes the independent DZ-Bench public `Predictions` shape.
DzDoc never imports DZ-Bench code.

The `evaluate-bundle` CLI consumes the published manifest plus a records array of
relative `image_path` values. It validates the complete public manifest, rejects
path traversal and unknown asset records, checks SHA-256 and dimensions, and
processes each verified raster page exactly once.
