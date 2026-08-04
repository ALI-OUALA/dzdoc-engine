"""Unicode-aware text normalization and lightweight routing heuristics."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .models import LanguageTag, ScriptTag, TextDirection

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


def assess_native_text(value: str) -> NativeTextQuality:
    """Conservative quality gate; presentation forms are not rejected by themselves."""

    if not value.strip():
        return NativeTextQuality(False, "ocr_required", 0.0, 0.0, "empty_text_layer")
    denominator = max(len(value), 1)
    replacement_ratio = value.count("\ufffd") / denominator
    controls = sum(unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in value)
    control_ratio = controls / denominator
    if replacement_ratio > 0.01:
        return NativeTextQuality(
            False, "ocr_required", replacement_ratio, control_ratio, "replacement_chars"
        )
    if control_ratio > 0.02:
        return NativeTextQuality(
            False, "ocr_required", replacement_ratio, control_ratio, "control_chars"
        )
    return NativeTextQuality(
        True, "native", replacement_ratio, control_ratio, "plausible_text_layer"
    )
