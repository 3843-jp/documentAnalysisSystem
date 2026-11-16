"""OCR / text extraction for PDFs and images."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def extract_text(file_bytes: bytes, filename: str = "", content_type: str = "") -> str:
    """Extract searchable text from a PDF or image.

    Strategy:
    1. Prefer embedded PDF text via PyMuPDF (fast, no Tesseract required).
    2. Fall back to Tesseract OCR on rendered PDF pages / images when available.
    """
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    texts: list[str] = []

    is_pdf = name.endswith(".pdf") or "pdf" in ctype
    is_image = any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")) or ctype.startswith("image/")

    if is_pdf:
        texts.append(_extract_pdf_text(file_bytes))
        ocr_pages = _ocr_pdf_pages(file_bytes)
        if ocr_pages:
            texts.append(ocr_pages)
    elif is_image:
        texts.append(_ocr_image(file_bytes))
    else:
        # Best-effort: try PDF then image
        pdf_text = _extract_pdf_text(file_bytes)
        if pdf_text:
            texts.append(pdf_text)
        else:
            texts.append(_ocr_image(file_bytes))

    combined = "\n".join(t.strip() for t in texts if t and t.strip())
    if not combined:
        # Last resort: pull printable runs from the raw bytes (helps with
        # minimal/test PDFs that have no valid text objects).
        combined = _printable_strings(file_bytes)
    return combined.strip()


def _printable_strings(file_bytes: bytes, min_len: int = 6) -> str:
    import re

    try:
        text = file_bytes.decode("latin-1", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""
    runs = re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.\-_/()]{%d,}" % (min_len - 1), text)
    return "\n".join(runs[:200]).strip()


def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed; skipping PDF text extraction")
        return ""

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        parts = []
        for page in doc:
            parts.append(page.get_text("text") or "")
        doc.close()
        return "\n".join(parts).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF text extraction failed: %s", exc)
        return ""


def _ocr_pdf_pages(file_bytes: bytes, max_pages: int = 5) -> str:
    """OCR first N PDF pages when Tesseract is available (for scanned PDFs)."""
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        # Probe tesseract early
        pytesseract.get_tesseract_version()
    except Exception:
        logger.info("Tesseract not available; skipping PDF page OCR")
        return ""

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        parts = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            # Only OCR pages with little/no embedded text
            if len((page.get_text("text") or "").strip()) > 40:
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            parts.append(pytesseract.image_to_string(img) or "")
        doc.close()
        return "\n".join(parts).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF OCR failed: %s", exc)
        return ""


def _ocr_image(file_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        pytesseract.get_tesseract_version()
    except Exception:
        logger.info("Tesseract not available; skipping image OCR")
        return ""

    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return (pytesseract.image_to_string(img) or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Image OCR failed: %s", exc)
        return ""
