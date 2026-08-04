"""Vendor-neutral stage boundaries for the hybrid cascade."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .ingestion import DocumentInput
from .models import Block, Document, Page, Provenance, TextSpan


@dataclass(frozen=True, slots=True)
class AdapterMetadata:
    name: str
    version: str
    upstream_project: str
    upstream_model: str | None
    licence: str
    supported_scripts: tuple[str, ...]
    supported_languages: tuple[str, ...]
    execution_providers: tuple[str, ...]
    input_format: str
    coordinate_system: str
    confidence_semantics: str
    required_assets: tuple[str, ...] = ()
    known_limitations: tuple[str, ...] = ()


class DocumentLoader(Protocol):
    def load(self, source: str | Path) -> DocumentInput: ...


class PdfInspector(Protocol):
    def inspect(self, document: DocumentInput) -> Any: ...


class PageRenderer(Protocol):
    def render(self, document: DocumentInput, page_index: int, dpi: int = 150) -> Any: ...


class ImagePreprocessor(Protocol):
    def preprocess(self, image: Any) -> Sequence[Any]: ...


class LayoutDetector(Protocol):
    def detect(self, image: Any) -> Sequence[Block]: ...


class TextDetector(Protocol):
    def detect(self, image: Any) -> Sequence[Any]: ...


class ScriptClassifier(Protocol):
    def classify(self, text_or_region: Any) -> tuple[str, str, str]: ...


class TextRecognizer(Protocol):
    metadata: AdapterMetadata

    def recognize(self, region: Any) -> Sequence[TextSpan]: ...


class CandidateFusion(Protocol):
    def fuse(self, candidates: Sequence[Any]) -> Any: ...


class ReadingOrderResolver(Protocol):
    def resolve(self, page: Page) -> Page: ...


class DocumentValidator(Protocol):
    def validate(self, document: Document) -> Sequence[Any]: ...


class VlmFallback(Protocol):
    def resolve(self, region: Any, *, provenance: Provenance) -> Any: ...


class DocumentPack(Protocol):
    name: str

    def extract(self, document: Document) -> dict[str, Any]: ...


class Exporter(Protocol):
    def export(self, document: Document, target: Path) -> Path: ...


class BenchmarkRunner(Protocol):
    def run(self, bundle: Path, output: Path) -> Path: ...
