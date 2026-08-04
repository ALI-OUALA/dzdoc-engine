# ADR 0002 — Deterministic OCR baseline

Status: accepted, 2026-08-04.

## Decision

Use the following CPU baseline behind DzDoc's vendor-neutral interfaces:

1. `PP-OCRv5_mobile_det` once per rendered page;
2. `arabic_PP-OCRv5_mobile_rec` as the first recognition and script-routing probe;
3. `latin_PP-OCRv5_mobile_rec` only when the Arabic result is low-confidence,
   empty, numeric/common, or script-inconsistent;
4. deterministic script/confidence/digit fusion with alternatives preserved;
5. Unicode logical text unchanged, with geometric line-band reading order;
6. no VLM in the default path.

All three weights are downloaded separately at immutable Hugging Face revisions
listed in `dzdoc.model_registry`. Installation never downloads weights. A benchmark
run should set `DZDOC_MODEL_DIR` to the pinned asset directory.

## Evidence

- PaddleOCR's official recognition documentation lists the Arabic model at 81.27%
  average recognition accuracy and the Latin model at 84.7% on their respective
  internal recognition sets. Those figures are model-vendor measurements and are
  not DzDoc quality claims.
- The official detector and both specialist model cards declare Apache-2.0.
- The mobile detector and specialist recognizers are materially smaller than the
  server variants and fit the required CPU baseline.
- Tesseract remains a useful external baseline, but its executable was absent from
  the measured workstation and it does not provide the chosen detect-once,
  specialist-routing architecture by itself.
- PaddleOCR-VL/Surya-class models remain escalation candidates, not default OCR,
  because the confirmed architecture requires deterministic cheap stages first.

Official sources:

- https://github.com/PaddlePaddle/PaddleOCR
- https://www.paddleocr.ai/main/en/version3.x/module_usage/text_detection.html
- https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html
- https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det
- https://huggingface.co/PaddlePaddle/arabic_PP-OCRv5_mobile_rec
- https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec

## Local measured checkpoint

Hardware: Intel Core i7-1360P, Windows, CPU execution, PaddleOCR 3.4.1,
PaddlePaddle 3.3.1, oneDNN disabled. Input: one original 1100×360 synthetic image
with one Arabic line, one French line, and one Arabic numeric line.

- cached process cold run: 23,328 ms;
- same-process warm run: 5,179 ms;
- model-load RSS increase: 291.88 MiB;
- text CER: 0.024096 (2 character errors / 83 reference characters);
- first Arabic and French lines: exact;
- Arabic decimal line: `٥٠` was recognized as `٠٠`, and comma style changed.

The first-ever asset acquisition took 227.9 s because Hugging Face transfer failed
and the downloader retried ModelScope. That is network provisioning time, not OCR
latency. This checkpoint is one synthetic page, not a product accuracy claim.

## Consequences

- Latin pages pay for an Arabic routing probe plus Latin recognition. This favors
  the Algerian Arabic-first product goal; DZ-Bench must test whether a future tiny
  script classifier reduces latency without harming routing.
- Paddle 3.3.1 oneDNN produced an unsupported PIR attribute exception on this CPU,
  so the adapter explicitly disables oneDNN. Re-enable only after a verified
  upstream fix and benchmark.
- Equation recognition, handwriting, semantic diagram understanding, table
  structure, and calibrated confidence remain separate measured work.
