from __future__ import annotations

import logging
from io import BytesIO

logger = logging.getLogger(__name__)

# Default recompression for typical lab PDFs.
_PDF_MAX_IMAGE_EDGE = 1600
_PDF_JPEG_QUALITY = 72

# Stronger settings when the upload is huge (phone/scanner dumps).
_PDF_LARGE_BYTES = 20 * 1024 * 1024
_PDF_AGGRESSIVE_EDGE = 1280
_PDF_AGGRESSIVE_QUALITY = 58
_PDF_RASTER_DPI = 130
_PDF_RASTER_QUALITY = 55


def compress_pdf(content: bytes, *, max_output_bytes: int | None = None) -> bytes:
    """Recompress embedded images and rewrite the PDF with deflate.

    For very large scans, falls back to rasterizing pages as JPEG if needed.
    Returns the original bytes when compression fails or does not shrink the file.
    """
    if not content or not content.lstrip().startswith(b"%PDF"):
        return content
    try:
        import fitz
    except Exception:
        return content

    aggressive = len(content) >= _PDF_LARGE_BYTES
    edge = _PDF_AGGRESSIVE_EDGE if aggressive else _PDF_MAX_IMAGE_EDGE
    quality = _PDF_AGGRESSIVE_QUALITY if aggressive else _PDF_JPEG_QUALITY

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        return content

    try:
        if document.page_count < 1:
            return content
        _recompress_embedded_images(document, max_edge=edge, jpeg_quality=quality)
        output = BytesIO()
        document.save(output, garbage=4, deflate=True, clean=True)
        compressed = output.getvalue()
    except Exception:
        logger.warning("PDF compression failed; keeping original bytes", exc_info=True)
        compressed = content
    finally:
        document.close()

    if not compressed or len(compressed) >= len(content):
        compressed = content

    if max_output_bytes is not None and len(compressed) > max_output_bytes:
        rasterized = _rasterize_pdf(content, dpi=_PDF_RASTER_DPI, jpeg_quality=_PDF_RASTER_QUALITY)
        if rasterized and len(rasterized) < len(compressed):
            compressed = rasterized

    return compressed


def _recompress_embedded_images(document, *, max_edge: int, jpeg_quality: int) -> None:
    from PIL import Image

    seen: set[int] = set()
    for page in document:
        for item in page.get_images(full=True):
            xref = int(item[0])
            if xref in seen:
                continue
            seen.add(xref)
            try:
                import fitz

                pixmap = fitz.Pixmap(document, xref)
            except Exception:
                continue
            try:
                if pixmap.n - pixmap.alpha >= 4:  # CMYK / multi-channel
                    pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                if pixmap.alpha:
                    pixmap = fitz.Pixmap(pixmap, 0)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                width, height = image.size
                longest = max(width, height)
                if longest > max_edge:
                    scale = max_edge / longest
                    image = image.resize(
                        (max(1, round(width * scale)), max(1, round(height * scale))),
                        Image.Resampling.BILINEAR,
                    )
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
                jpeg_bytes = buffer.getvalue()
                if not jpeg_bytes:
                    continue
                page.replace_image(xref, stream=jpeg_bytes)
            except Exception:
                continue


def _rasterize_pdf(content: bytes, *, dpi: int, jpeg_quality: int) -> bytes | None:
    """Last-resort shrink for enormous scan PDFs: redraw pages as JPEG images."""
    try:
        import fitz
    except Exception:
        return None
    try:
        source = fitz.open(stream=content, filetype="pdf")
    except Exception:
        return None
    try:
        if source.page_count < 1:
            return None
        target = fitz.open()
        scale = dpi / 72
        matrix = fitz.Matrix(scale, scale)
        for page in source:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            jpeg_bytes = pixmap.tobytes("jpeg", jpg_quality=jpeg_quality)
            new_page = target.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=jpeg_bytes)
        output = BytesIO()
        target.save(output, garbage=4, deflate=True, clean=True)
        target.close()
        return output.getvalue()
    except Exception:
        logger.warning("PDF raster compression failed", exc_info=True)
        return None
    finally:
        source.close()
