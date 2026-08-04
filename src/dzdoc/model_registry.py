"""Reviewed OCR assets; revisions are immutable Hugging Face commits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelAsset:
    name: str
    repo_id: str
    revision: str
    licence: str = "Apache-2.0"


OCR_ASSETS = (
    ModelAsset(
        "PP-OCRv5_mobile_det",
        "PaddlePaddle/PP-OCRv5_mobile_det",
        "0d63e78e2b680928f6b1747d76a08db6e645efb7",
    ),
    ModelAsset(
        "arabic_PP-OCRv5_mobile_rec",
        "PaddlePaddle/arabic_PP-OCRv5_mobile_rec",
        "33d91636a65dca87f5562cc48860332ae367ee1b",
    ),
    ModelAsset(
        "latin_PP-OCRv5_mobile_rec",
        "PaddlePaddle/latin_PP-OCRv5_mobile_rec",
        "ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57",
    ),
)


ASSET_BY_NAME = {asset.name: asset for asset in OCR_ASSETS}
