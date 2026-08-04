"""Unicode-aware text normalization and lightweight routing heuristics."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .models import LanguageTag, ProcessingWarning, ScriptTag, TextDirection

_BIDI_CONTROLS = frozenset(
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)
_ARABIC_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_display(value: str) -> str:
    """Apply NFC and remove only bidi formatting controls; never reverse text."""

    return "".join(
        char for char in unicodedata.normalize("NFC", value) if char not in _BIDI_CONTROLS
    )


def normalize_search(value: str) -> str:
    """Create optional matching text without changing stored display evidence."""

    display = normalize_display(value).replace("ـ", "")
    display = "".join(char for char in display if unicodedata.category(char) != "Mn")
    display = display.translate(_ARABIC_DIGIT_TRANSLATION).lower()
    return " ".join(display.split())


def normalization_warnings(value: str) -> list[ProcessingWarning]:
    """Report display repairs while keeping the original text untouched."""

    if any(char in _BIDI_CONTROLS for char in value):
        return [
            ProcessingWarning(
                code="bidi_controls_removed",
                message="Bidi formatting controls were removed from normalized display text.",
                stage="text_normalization",
            )
        ]
    return []


def classify_text(value: str) -> tuple[LanguageTag, ScriptTag, TextDirection]:
    arabic = 0
    latin = 0
    rtl = 0
    ltr = 0
    for char in value:
        name = unicodedata.name(char, "")
        bidi = unicodedata.bidirectional(char)
        arabic += int("ARABIC" in name)
        latin += int("LATIN" in name)
        rtl += int(bidi in {"R", "AL"})
        ltr += int(bidi == "L")
    if arabic and latin:
        script = ScriptTag.MIXED
        language = LanguageTag.MIXED
    elif arabic:
        script = ScriptTag.ARABIC
        language = LanguageTag.ARABIC
    elif latin:
        script = ScriptTag.LATIN
        language = LanguageTag.FRENCH
    else:
        script = ScriptTag.COMMON if value.strip() else ScriptTag.UNKNOWN
        language = LanguageTag.UNKNOWN
    if rtl and ltr:
        direction = TextDirection.MIXED
    elif rtl:
        direction = TextDirection.RTL
    elif ltr:
        direction = TextDirection.LTR
    else:
        direction = TextDirection.UNKNOWN
    return language, script, direction


@dataclass(frozen=True, slots=True)
class NativeTextQuality:
    accepted: bool
    route: str
    replacement_ratio: float
    control_ratio: float
    reason: str
    image_coverage: float = 0.0


def assess_native_text(value: str, *, image_coverage: float = 0.0) -> NativeTextQuality:
    """Conservative quality gate; presentation forms are not rejected by themselves."""

    image_coverage = min(1.0, max(0.0, float(image_coverage)))
    if not value.strip():
        return NativeTextQuality(
            False, "ocr_required", 0.0, 0.0, "empty_text_layer", image_coverage
        )
    denominator = max(len(value), 1)
    replacement_ratio = value.count("\ufffd") / denominator
    controls = sum(unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in value)
    control_ratio = controls / denominator
    private_use_ratio = sum(unicodedata.category(char) == "Co" for char in value) / denominator
    if replacement_ratio > 0.01:
        return NativeTextQuality(
            False,
            "ocr_required",
            replacement_ratio,
            control_ratio,
            "replacement_chars",
            image_coverage,
        )
    if control_ratio > 0.005:
        return NativeTextQuality(
            False,
            "ocr_required",
            replacement_ratio,
            control_ratio,
            "control_chars",
            image_coverage,
        )
    if private_use_ratio > 0.005:
        return NativeTextQuality(
            False,
            "ocr_required",
            replacement_ratio,
            control_ratio,
            "private_use_glyphs",
            image_coverage,
        )
    visible = [char for char in value if not char.isspace()]
    if len(visible) < 32 and image_coverage > 0.15:
        return NativeTextQuality(
            False,
            "ocr_required",
            replacement_ratio,
            control_ratio,
            "sparse_overlay_on_image",
            image_coverage,
        )
    if len(visible) >= 20:
        alphanumeric_ratio = sum(char.isalnum() for char in visible) / len(visible)
        dominant_ratio = max(value.count(char) for char in set(visible)) / len(visible)
        if alphanumeric_ratio < 0.15:
            return NativeTextQuality(
                False,
                "ocr_required",
                replacement_ratio,
                control_ratio,
                "implausible_glyphs",
                image_coverage,
            )
        if dominant_ratio > 0.50:
            return NativeTextQuality(
                False,
                "ocr_required",
                replacement_ratio,
                control_ratio,
                "repeated_glyphs",
                image_coverage,
            )
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) >= 4 and len(set(lines)) / len(lines) < 0.35:
        return NativeTextQuality(
            False,
            "ocr_required",
            replacement_ratio,
            control_ratio,
            "phantom_repeated_lines",
            image_coverage,
        )
    return NativeTextQuality(
        True,
        "native",
        replacement_ratio,
        control_ratio,
        "plausible_text_layer",
        image_coverage,
    )
