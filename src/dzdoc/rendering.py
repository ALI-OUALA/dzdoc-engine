"""Page rendering adapters used only after the native-text quality gate."""

from __future__ import annotations

from .ingestion import DocumentInput, IngestionError
from .native_pdf import PdfInspectionError


class PdfiumRenderer:
    def render(self, document: DocumentInput, page_index: int, dpi: int = 150):
        if page_index < 0 or dpi <= 0:
            raise ValueError("page_index must be non-negative and dpi must be positive")
        try:
            import numpy as np
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise PdfInspectionError(
                "pypdfium2 and NumPy are required to render OCR pages"
            ) from exc
        pdf = page = bitmap = None
        try:
            pdf = pdfium.PdfDocument(document.data)
            if page_index >= len(pdf):
                raise IngestionError("PDF page index is out of range")
            page = pdf[page_index]
            bitmap = page.render(scale=dpi / 72, rev_byteorder=True)
            pil_image = bitmap.to_pil().convert("RGB")
            try:
                return np.array(pil_image, dtype=np.uint8, copy=True)
            finally:
                pil_image.close()
        except Exception as exc:
            if isinstance(exc, IngestionError):
                raise
            raise PdfInspectionError(f"PDF page rendering failed: {exc}") from exc
        finally:
            try:
                if bitmap is not None:
                    bitmap.close()
            finally:
                try:
                    if page is not None:
                        page.close()
                finally:
                    if pdf is not None:
                        pdf.close()


def decode_image(document: DocumentInput, *, max_pixels: int):
    if max_pixels <= 0:
        raise ValueError("max_pixels must be positive")
    try:
        from io import BytesIO

        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise PdfInspectionError("Pillow and NumPy are required to decode images") from exc
    try:
        with Image.open(BytesIO(document.data)) as source:
            if source.width * source.height > max_pixels:
                raise IngestionError("image exceeds decoded pixel limit")
            image = source.convert("RGB")
            return np.array(image, dtype=np.uint8, copy=True)
    except IngestionError:
        raise
    except Image.DecompressionBombError as exc:
        raise IngestionError("image exceeds Pillow's decompression safety limit") from exc
    except Exception as exc:
        raise PdfInspectionError(f"image decoding failed: {exc}") from exc
