"""Pinned PaddleOCR-VL adapter for guarded region-level escalation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .fallback import VlmFallbackResult
from .model_registry import VLM_ASSETS
from .ocr import DetectedRegion, OcrDependencyError, _crop

_ASSET = VLM_ASSETS[0]


class PaddleOcrVlFallback:
    """Optional local-only PaddleOCR-VL-1.6 fallback; never downloads implicitly."""

    name = "paddleocr-vl-guarded"
    version = "1.0.0"
    model_name = _ASSET.repo_id
    model_revision = _ASSET.revision

    def __init__(
        self,
        model_root: str | Path,
        *,
        pipeline_factory: Callable[[Path], Any] | None = None,
    ) -> None:
        self.model_root = Path(model_root).expanduser().resolve()
        if not self.model_root.is_dir():
            raise ValueError("VLM model root must be an existing local directory")
        self._factory = pipeline_factory or _official_pipeline
        self._pipeline: Any | None = None

    def resolve(self, image: Any, region: DetectedRegion) -> VlmFallbackResult:
        if self._pipeline is None:
            self._pipeline = self._factory(self.model_root)
        assert self._pipeline is not None
        crop = _crop(image, region)
        results = list(self._pipeline.predict(crop))
        if not results:
            raise RuntimeError("PaddleOCR-VL returned no result")
        raw = _result_payload(results[0])
        text = _result_text(raw)
        confidence = _result_confidence(raw)
        return VlmFallbackResult(
            text=text,
            confidence=confidence,
            raw_output=raw,
            prompt_label="ocr_region_verbatim",
            decoding={"temperature": 0.0, "local_assets_only": True},
        )


def _official_pipeline(model_root: Path) -> Any:
    try:
        from paddleocr import PaddleOCRVL  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise OcrDependencyError("PaddleOCR-VL requires dzdoc[vlm-paddle]") from exc
    try:
        return PaddleOCRVL(
            pipeline_version="v1.6",
            vl_rec_model_dir=str(model_root),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_layout_detection=False,
        )
    except TypeError as exc:
        raise OcrDependencyError(
            "Installed PaddleOCR does not expose the reviewed PaddleOCRVL 1.6 API"
        ) from exc


def _result_payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", result)
    if callable(payload):
        payload = payload()
    if isinstance(payload, dict):
        value = payload.get("res", payload)
        return value if isinstance(value, dict) else {"result": value}
    return {"result": str(payload)}


def _result_text(payload: dict[str, Any]) -> str:
    for key in ("rec_text", "text", "markdown", "parsing_res_list"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
            parts = [_item_text(item) for item in value]
            if text := "\n".join(part for part in parts if part):
                return text
    raise RuntimeError("PaddleOCR-VL result contains no recognized text")


def _item_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("content", "text", "rec_text", "block_content"):
            if isinstance(item.get(key), str):
                return item[key].strip()
    return ""


def _result_confidence(payload: dict[str, Any]) -> float:
    for key in ("rec_score", "confidence", "score"):
        value = payload.get(key)
        if isinstance(value, int | float):
            return max(0.0, min(1.0, float(value)))
    # PaddleOCR-VL parsing output does not currently expose a calibrated region score.
    return 0.82


__all__ = ["PaddleOcrVlFallback"]
