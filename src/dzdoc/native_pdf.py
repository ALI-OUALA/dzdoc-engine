"""Optional native PDF inspection adapter and page-level quality evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .ingestion import DocumentInput, IngestionError
from .text import NativeTextQuality, assess_native_text


class PdfInspectionError(RuntimeError):
    """Raised when native PDF inspection cannot be performed."""


@dataclass(frozen=True, slots=True)
class NativePage:
    page_index: int
    text: str
    width: int
    height: int
    quality: NativeTextQuality


@dataclass(frozen=True, slots=True)
class PdfInspection:
    page_count: int
    pages: tuple[NativePage, ...]
    adapter: str
    adapter_version: str


class NativePdfInspector:
    """Use PyMuPDF when installed; keep dependency outside core imports."""

    def inspect(self, document: DocumentInput) -> PdfInspection:
        if document.kind != "pdf":
            raise IngestionError("native PDF inspector received a non-PDF document")
        try:
            import fitz  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PdfInspectionError(
                "PyMuPDF is required for native PDF inspection; install dzdoc[pdf]"
            ) from exc
        try:
            pdf = fitz.open(stream=document.data, filetype="pdf")
            pages = tuple(
                NativePage(
                    page_index=index,
                    text=page.get_text("text"),
                    width=max(1, round(float(page.rect.width))),
                    height=max(1, round(float(page.rect.height))),
                    quality=assess_native_text(page.get_text("text")),
                )
                for index, page in enumerate(pdf)
            )
            pdf.close()
        except Exception as exc:  # PyMuPDF exposes several parser exception types.
            raise PdfInspectionError(f"PDF inspection failed: {exc}") from exc
        return PdfInspection(
            page_count=len(pages),
            pages=pages,
            adapter="pymupdf",
            adapter_version=str(fitz.VersionBind),
        )
