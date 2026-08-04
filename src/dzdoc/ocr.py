"""Deterministic detect-once OCR adapter and candidate fusion."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import hypot, isfinite
from pathlib import Path
from typing import Any

from .contracts import AdapterMetadata
from .model_registry import ASSET_BY_NAME, OCR_ASSETS
from .models import BoundingBox, ProcessingWarning, ScriptTag
from .text import classify_text


class OcrDependencyError(RuntimeError):
    """Raised when the optional OCR runtime is unavailable."""


@dataclass(frozen=True, slots=True)
class DetectedRegion:
    polygon: tuple[tuple[float, float], ...]
    confidence: float

    def __post_init__(self) -> None:
        if len(self.polygon) < 2:
            raise ValueError("detected region requires at least two points")
        if not all(isfinite(value) for point in self.polygon for value in point):
            raise ValueError("detected region coordinates must be finite")
        if not 0 <= self.confidence <= 1:
            raise ValueError("detected region confidence must be between 0 and 1")

    @property
    def bbox(self) -> BoundingBox:
        xs = [point[0] for point in self.polygon]
        ys = [point[1] for point in self.polygon]
        return BoundingBox(
            x=max(0, min(xs)),
            y=max(0, min(ys)),
            width=max(1, max(xs) - min(xs)),
            height=max(1, max(ys) - min(ys)),
        )


@dataclass(frozen=True, slots=True)
class Recognition:
    text: str
    confidence: float
    adapter: str
    expected_script: str


@dataclass(frozen=True, slots=True)
class FusedRecognition:
    selected: Recognition
    alternatives: tuple[Recognition, ...]
    confidence: float
    warnings: tuple[ProcessingWarning, ...]


def _script_consistency(candidate: Recognition) -> float:
    _, script, _ = classify_text(candidate.text)
    if script == ScriptTag.COMMON:
        return 0.8
    if script.value == candidate.expected_script:
        return 1.0
    if script == ScriptTag.MIXED:
        return 0.7
    return 0.15


def _digits(text: str) -> str:
    import unicodedata

    return "".join(str(unicodedata.digit(char)) for char in text if char.isdecimal())


def candidate_score(candidate: Recognition) -> float:
    """Score recognizer evidence outside vendor adapters."""

    return min(1.0, 0.85 * candidate.confidence + 0.15 * _script_consistency(candidate))


def fuse_recognitions(
    candidates: list[Recognition], *, ambiguity_margin: float = 0.08
) -> FusedRecognition:
    if not candidates:
        raise ValueError("at least one recognition candidate is required")
    ranked = sorted(candidates, key=candidate_score, reverse=True)
    selected = ranked[0]
    warnings: list[ProcessingWarning] = []
    if (
        len(ranked) > 1
        and candidate_score(ranked[0]) - candidate_score(ranked[1]) < ambiguity_margin
    ):
        warnings.append(
            ProcessingWarning(
                code="ambiguous_recognition",
                message="Top Arabic/French candidates are close; alternative preserved.",
                stage="candidate_fusion",
            )
        )
    digit_sets = {_digits(candidate.text) for candidate in ranked if _digits(candidate.text)}
    if len(digit_sets) > 1:
        warnings.append(
            ProcessingWarning(
                code="digit_disagreement",
                message="Recognizers disagree on the logical digit sequence.",
                stage="candidate_fusion",
            )
        )
    confidence = candidate_score(selected)
    if warnings:
        confidence = max(0.0, confidence - 0.12)
    return FusedRecognition(selected, tuple(ranked[1:]), confidence, tuple(warnings))


def order_recognized_regions(
    items: list[tuple[DetectedRegion, FusedRecognition]], *, line_tolerance: float = 0.6
) -> list[tuple[DetectedRegion, FusedRecognition]]:
    """Order horizontal bands top-to-bottom, then preserve their dominant direction."""

    if not items:
        return []
    by_y = sorted(items, key=lambda item: (item[0].bbox.y, item[0].bbox.x))
    bands: list[list[tuple[DetectedRegion, FusedRecognition]]] = []
    for item in by_y:
        if not bands:
            bands.append([item])
            continue
        band_y = sum(value[0].bbox.y for value in bands[-1]) / len(bands[-1])
        height = max(value[0].bbox.height for value in bands[-1])
        if abs(item[0].bbox.y - band_y) <= max(4.0, height * line_tolerance):
            bands[-1].append(item)
        else:
            bands.append([item])
    ordered: list[tuple[DetectedRegion, FusedRecognition]] = []
    for band in bands:
        rtl = sum(classify_text(item[1].selected.text)[2].value == "rtl" for item in band)
        band.sort(key=lambda item: item[0].bbox.x, reverse=rtl >= len(band) / 2)
        ordered.extend(band)
    return ordered


class PaddleOcrEngine:
    """Official PP-OCR models: one detector, Arabic-first routed recognition."""

    name = "paddleocr-specialist-cascade"
    version = "paddleocr-3.4.1"
    metadata = AdapterMetadata(
        name=name,
        version=version,
        upstream_project="PaddlePaddle/PaddleOCR",
        upstream_model="PP-OCRv5_mobile_det + Arabic/Latin PP-OCRv5 mobile recognizers",
        licence="Apache-2.0",
        supported_scripts=("Arabic", "Latin", "Common"),
        supported_languages=("ar", "fr"),
        execution_providers=("cpu",),
        input_format="RGB numpy page / quadrilateral crop",
        coordinate_system="pixel, top-left origin",
        confidence_semantics="uncalibrated model probability fused with script consistency",
        required_assets=(
            "PP-OCRv5_mobile_det",
            "arabic_PP-OCRv5_mobile_rec",
            "latin_PP-OCRv5_mobile_rec",
        ),
        known_limitations=(
            "Arabic recognizer is the routing probe, so Latin regions require two recognitions.",
            "Paddle 3.3 CPU oneDNN is disabled due an observed unsupported PIR attribute error.",
        ),
    )

    def __init__(
        self,
        *,
        cpu_threads: int = 8,
        route_threshold: float = 0.82,
        model_root: str | Path | None = None,
        recognition_mode: str = "routed",
        allow_unpinned_download: bool = False,
    ) -> None:
        if recognition_mode not in {"routed", "arabic", "latin"}:
            raise ValueError("recognition_mode must be routed, arabic, or latin")
        if cpu_threads <= 0:
            raise ValueError("cpu_threads must be positive")
        if not 0 < route_threshold <= 1:
            raise ValueError("route_threshold must be greater than 0 and at most 1")
        self.cpu_threads = cpu_threads
        self.route_threshold = route_threshold
        self.recognition_mode = recognition_mode
        self.allow_unpinned_download = allow_unpinned_download
        self.name = f"paddleocr-{recognition_mode}"
        configured_root = model_root or os.environ.get("DZDOC_MODEL_DIR")
        self.model_root = Path(configured_root).resolve() if configured_root else None
        self._detector: Any = None
        self._arabic: Any = None
        self._latin: Any = None

    def _classes(self):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        try:
            from paddleocr import TextDetection, TextRecognition
        except ImportError as exc:
            raise OcrDependencyError("install the optional dzdoc[ocr-paddle] extra") from exc
        return TextDetection, TextRecognition

    def _common(self) -> dict[str, Any]:
        return {
            "device": "cpu",
            "cpu_threads": self.cpu_threads,
            "enable_mkldnn": False,
        }

    @property
    def asset_revisions(self) -> str:
        return ",".join(f"{asset.name}@{asset.revision}" for asset in OCR_ASSETS)

    def _model_args(self, name: str) -> dict[str, str]:
        if self.model_root is None:
            if not self.allow_unpinned_download:
                raise OcrDependencyError(
                    "pinned OCR assets are required; set DZDOC_MODEL_DIR or explicitly "
                    "enable allow_unpinned_download"
                )
            return {"model_name": name}
        path = self.model_root / ASSET_BY_NAME[name].name
        if not path.is_dir():
            raise OcrDependencyError(f"pinned model directory is missing: {path}")
        return {"model_name": name, "model_dir": str(path)}

    def detect(self, image: Any) -> list[DetectedRegion]:
        TextDetection, _ = self._classes()
        if self._detector is None:
            self._detector = TextDetection(
                **self._model_args("PP-OCRv5_mobile_det"), **self._common()
            )
        payload = self._detector.predict(image, batch_size=1)[0].json["res"]
        return [
            DetectedRegion(tuple(tuple(map(float, point)) for point in polygon), float(score))
            for polygon, score in zip(payload["dt_polys"], payload["dt_scores"], strict=True)
        ]

    def recognize(self, image: Any, region: DetectedRegion) -> list[Recognition]:
        crop = _crop(image, region)
        _, TextRecognition = self._classes()
        if self.recognition_mode == "latin":
            if self._latin is None:
                self._latin = TextRecognition(
                    **self._model_args("latin_PP-OCRv5_mobile_rec"), **self._common()
                )
            return [_predict(self._latin, crop, "latin_PP-OCRv5_mobile_rec", "latin")]
        if self._arabic is None:
            self._arabic = TextRecognition(
                **self._model_args("arabic_PP-OCRv5_mobile_rec"), **self._common()
            )
        arabic = _predict(self._arabic, crop, "arabic_PP-OCRv5_mobile_rec", "arabic")
        candidates = [arabic]
        if self.recognition_mode == "arabic":
            return candidates
        _, script, _ = classify_text(arabic.text)
        uncertain = (
            arabic.confidence < self.route_threshold
            or script not in {ScriptTag.ARABIC, ScriptTag.MIXED}
            or not arabic.text.strip()
        )
        if uncertain:
            if self._latin is None:
                self._latin = TextRecognition(
                    **self._model_args("latin_PP-OCRv5_mobile_rec"), **self._common()
                )
            candidates.append(_predict(self._latin, crop, "latin_PP-OCRv5_mobile_rec", "latin"))
        return candidates


def _predict(model: Any, crop: Any, adapter: str, script: str) -> Recognition:
    payload = model.predict(crop, batch_size=1)[0].json["res"]
    return Recognition(
        text=str(payload.get("rec_text", "")),
        confidence=float(payload.get("rec_score", 0.0)),
        adapter=adapter,
        expected_script=script,
    )


def _crop(image: Any, region: DetectedRegion) -> Any:
    """Perspective-normalize one quadrilateral without a second detection pass."""

    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise OcrDependencyError("OpenCV and NumPy are required by dzdoc[ocr-paddle]") from exc
    points = np.asarray(region.polygon, dtype="float32")
    if len(points) != 4:
        box = region.bbox
        return image[int(box.y) : int(box.y + box.height), int(box.x) : int(box.x + box.width)]
    width = max(hypot(*(points[1] - points[0])), hypot(*(points[2] - points[3])))
    height = max(hypot(*(points[3] - points[0])), hypot(*(points[2] - points[1])))
    target = np.asarray(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(points, target)
    return cv2.warpPerspective(image, matrix, (max(1, round(width)), max(1, round(height))))
