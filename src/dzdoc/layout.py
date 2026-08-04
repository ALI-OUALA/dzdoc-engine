"""Small deterministic block semantics independent of OCR vendors."""

from __future__ import annotations

import re

from .models import BlockType, BoundingBox
from .text import normalize_search

_EQUATION = re.compile(r"(?:[=≈≤≥∑∫√]|\b[fg]\s*\(|\b(?:sin|cos|lim)\b)", re.IGNORECASE)
_EXERCISE = re.compile(r"(?:التمرين|exercice)\s*(?:\w+|\d+)", re.IGNORECASE)
_INSTRUCTION = re.compile(
    r"(?:أجب|احسب|استنتج|برهن|répondez|calculer|déduire|justifier|consigne)",
    re.IGNORECASE,
)
_TITLE = re.compile(r"(?:بكالوريا|اختبار|baccalauréat|épreuve|sujet)", re.IGNORECASE)


def classify_block_type(
    text: str, bbox: BoundingBox, *, page_width: int, page_height: int
) -> BlockType:
    normalized = normalize_search(text)
    if normalized.isdecimal() and bbox.y > page_height * 0.85:
        return BlockType.PAGE_NUMBER
    if _EQUATION.search(normalized):
        return BlockType.EQUATION
    if _EXERCISE.search(normalized):
        return BlockType.EXERCISE
    if _INSTRUCTION.search(normalized):
        return BlockType.INSTRUCTION
    if _TITLE.search(normalized) and bbox.y < page_height * 0.25:
        return BlockType.TITLE
    return BlockType.PARAGRAPH
