# Third-party notices

| Component | Use | Licence/status |
| --- | --- | --- |
| Pydantic | typed canonical models and validation | MIT; declared dependency |
| Typer | CLI | MIT; declared dependency |
| NumPy | OCR image arrays and tests | BSD-3-Clause; OCR/dev extras |
| psutil | benchmark peak RSS sampling | BSD-3-Clause; OCR/dev extras |
| huggingface-hub | explicit model asset download script | Apache-2.0; OCR extra |
| pypdfium2 / PDFium | optional native PDF inspection and rendering | pypdfium2 Apache-2.0/BSD-3-Clause; bundled PDFium and third-party notices also apply |
| Pillow | image decoding and tests | HPND; OCR/dev extras |
| Pyright | static type checking | MIT; development dependency |
| FastAPI / Starlette / Uvicorn | optional HTTP service | MIT / BSD-3-Clause; service extra |
| SQLAlchemy / psycopg | metadata, queue, PostgreSQL adapter | MIT / LGPL-3.0 with linking exception; service extra |
| boto3 | optional S3-compatible object store | Apache-2.0; s3 extra |
| React / Vite / Lucide | review web application and icons | MIT / MIT / ISC |
| PostgreSQL / nginx | operator-supplied deployment services | PostgreSQL / BSD-2-Clause; not linked into project code |

No model weights, benchmark documents, or copied document content are included.

PyMuPDF was removed before this phase was committed because its AGPL/commercial
licensing did not fit the repository dependency policy.

# OCR runtime and reviewed model assets

The optional `ocr-paddle` extra uses PaddleOCR and PaddlePaddle under Apache-2.0.
It also installs their transitive dependencies; exact versions are recorded in
`uv.lock`.

Reviewed Apache-2.0 model assets (not redistributed in this repository):

- `PaddlePaddle/PP-OCRv5_mobile_det` at
  `0d63e78e2b680928f6b1747d76a08db6e645efb7`;
- `PaddlePaddle/arabic_PP-OCRv5_mobile_rec` at
  `33d91636a65dca87f5562cc48860332ae367ee1b`;
- `PaddlePaddle/latin_PP-OCRv5_mobile_rec` at
  `ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57`.
- `PaddlePaddle/PaddleOCR-VL-1.6` at
  `c5630abae1d940eafe0697512a0325494b02ab42` (optional guarded fallback).

Weights are fetched from their official Hugging Face repositories only when the
operator runs `scripts/fetch_models.py`; they are never committed or downloaded
during installation or tests.
