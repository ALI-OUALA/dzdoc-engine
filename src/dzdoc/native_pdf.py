"""Liberal-licensed PDFium native-text inspection and quality evidence."""

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
    """Use pypdfium2 when installed; keep the adapter outside core imports."""

    def __init__(self, *, max_pages: int = 200) -> None:
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        self.max_pages = max_pages

    def inspect(self, document: DocumentInput) -> PdfInspection:
        if document.kind != "pdf":
            raise IngestionError("native PDF inspector received a non-PDF document")
        try:
            import pypdfium2 as pdfium
            import pypdfium2.raw as pdfium_c
        except ImportError as exc:
            raise PdfInspectionError(
                "pypdfium2 is required for native PDF inspection; install dzdoc[pdf]"
            ) from exc
        pdf = None
        try:
            pdf = pdfium.PdfDocument(document.data)
            page_count = len(pdf)
            if page_count <= 0:
                raise PdfInspectionError("PDF contains no pages")
            if page_count > self.max_pages:
                raise PdfInspectionError(f"PDF exceeds {self.max_pages} page limit")
            pages_list: list[NativePage] = []
            for index in range(page_count):
                page = None
                text_page = None
                try:
                    page = pdf[index]
                    text_page = page.get_textpage()
                    text = str(text_page.get_text_range() or "")
                    width, height = page.get_size()
                    image_coverage = _image_coverage(page, pdfium_c, width, height)
                    pages_list.append(
                        NativePage(
                            page_index=index,
                            text=text,
                            width=max(1, round(float(width))),
                            height=max(1, round(float(height))),
                            quality=assess_native_text(text, image_coverage=image_coverage),
                        )
                    )
                finally:
                    try:
                        if text_page is not None:
                            text_page.close()
                    finally:
                        if page is not None:
                            page.close()
            pages = tuple(pages_list)
        except PdfInspectionError:
            raise
        except Exception as exc:
            raise PdfInspectionError(f"PDF inspection failed: {exc}") from exc
        finally:
            if pdf is not None:
                pdf.close()
        return PdfInspection(
            page_count=len(pages),
            pages=pages,
            adapter="pypdfium2",
            adapter_version=str(pdfium.PYPDFIUM_INFO.version),
        )


def _image_coverage(page, pdfium_c, width: float, height: float) -> float:
    """Estimate raster coverage without making object inspection a parse failure."""

    try:
        objects = page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE])
    except Exception:
        return 0.0
    area = 0.0
    for image in objects:
        try:
            left, bottom, right, top = image.get_bounds()
            area += abs((right - left) * (top - bottom))
        except Exception:
            continue
    return min(1.0, max(0.0, area / max(float(width) * float(height), 1.0)))
