"""Guarded, deterministic validation for optional region-level VLM output."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .ocr import FusedRecognition, Recognition, candidate_score
from .text import classify_text


@dataclass(frozen=True, slots=True)
class VlmFallbackResult:
    text: str
    confidence: float
    raw_output: dict[str, Any]
    prompt_label: str
    decoding: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    accepted: bool
    reason: str
    recognition: Recognition | None = None


def validate_fallback(
    deterministic: FusedRecognition,
    result: VlmFallbackResult,
    *,
    adapter: str,
    model: str,
    model_revision: str,
    max_output_chars: int,
    minimum_gain: float,
) -> FallbackDecision:
    text = result.text.strip()
    if not text:
        return FallbackDecision(False, "empty_output")
    if len(text) > max_output_chars:
        return FallbackDecision(False, "output_too_long")
    has_control = any(
        unicodedata.category(character) == "Cc" and character not in "\n\t" for character in text
    )
    if has_control:
        return FallbackDecision(False, "control_characters")
    deterministic_numbers = {
        _numbers(candidate.text)
        for candidate in (deterministic.selected, *deterministic.alternatives)
        if _numbers(candidate.text)
    }
    if len(deterministic_numbers) == 1 and _numbers(text) != next(iter(deterministic_numbers)):
        return FallbackDecision(False, "digit_conflict")
    _, script, _ = classify_text(text)
    recognition = Recognition(
        text=text,
        confidence=max(0.0, min(1.0, result.confidence)),
        adapter=adapter,
        expected_script=script.value,
        kind="vlm",
        model=model,
        model_revision=model_revision,
        details={"prompt_label": result.prompt_label, **result.decoding},
    )
    if candidate_score(recognition) < deterministic.confidence + minimum_gain:
        return FallbackDecision(False, "insufficient_gain")
    return FallbackDecision(True, "validated", recognition)


_NUMBER = re.compile(r"[0-9٠-٩۰-۹][0-9٠-٩۰-۹ .,\u00a0]*")


def _numbers(text: str) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for match in _NUMBER.finditer(text):
        token = (
            "".join(
                str(unicodedata.digit(character)) if character.isdecimal() else character
                for character in match.group().strip(" .,\u00a0")
            )
            .replace(" ", "")
            .replace("\u00a0", "")
        )
        if not token:
            continue
        if "," in token and "." in token:
            decimal_mark = "," if token.rfind(",") > token.rfind(".") else "."
            thousands_mark = "." if decimal_mark == "," else ","
            token = token.replace(thousands_mark, "").replace(decimal_mark, ".")
        elif "," in token or "." in token:
            mark = "," if "," in token else "."
            parts = token.split(mark)
            token = "".join(parts) if len(parts) > 2 or len(parts[-1]) == 3 else ".".join(parts)
        try:
            values.append(Decimal(token))
        except InvalidOperation:
            continue
    return tuple(values)


__all__ = ["FallbackDecision", "VlmFallbackResult", "validate_fallback"]
