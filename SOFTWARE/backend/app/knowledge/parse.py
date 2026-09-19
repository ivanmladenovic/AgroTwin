from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.ocr import ocr_png, tesseract_available
from app.knowledge.pdf import extract_pdf_pages


@dataclass
class ParsedPage:
    page_number: int
    raw_text: str
    has_text_layer: bool
    ocr_used: bool
    image_png: bytes | None = None
    embedded_images: list[bytes] = field(default_factory=list)


def parse_pdf_pages(content: bytes, *, dpi: int = 160, ocr_empty_pages: bool = True) -> list[ParsedPage]:
    text_by_page = {number: text for number, text in extract_pdf_pages(content)}
    rendered = _render_pages(content, dpi=dpi)
    if rendered:
        page_count = len(rendered)
    else:
        page_count = max(text_by_page.keys(), default=0)

    pages: list[ParsedPage] = []
    for index in range(1, page_count + 1):
        layer = (text_by_page.get(index) or "").strip()
        image_png = rendered[index - 1][0] if rendered else None
        embedded = rendered[index - 1][1] if rendered else []
        ocr_used = False
        raw = layer
        if len(raw) < 40 and ocr_empty_pages and image_png and tesseract_available():
            raw = ocr_png(image_png)
            ocr_used = True
        if index == 1 or index % 5 == 0 or index == page_count:
            print(f"  parse page {index}/{page_count} ocr={ocr_used} chars={len(raw)}", flush=True)
        pages.append(
            ParsedPage(
                page_number=index,
                raw_text=raw,
                has_text_layer=bool(layer),
                ocr_used=ocr_used,
                image_png=image_png,
                embedded_images=embedded,
            )
        )
    return pages


def _render_pages(content: bytes, *, dpi: int) -> list[tuple[bytes, list[bytes]]] | None:
    try:
        import fitz
    except ImportError:
        return None
    document = fitz.open(stream=content, filetype="pdf")
    rendered: list[tuple[bytes, list[bytes]]] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    for page in document:
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        page_image = pixmap.tobytes("jpeg")
        extracted_images: list[bytes] = []
        for info in page.get_images(full=True):
            xref = info[0]
            try:
                extracted = document.extract_image(xref)
            except Exception:
                continue
            data = extracted.get("image")
            if data and len(data) > 8000:
                extracted_images.append(data)
        if len(extracted_images) == 1 and len(extracted_images[0]) > 400_000:
            figures: list[bytes] = []
        else:
            figures = [blob for blob in extracted_images if len(blob) < 8_000_000]
        rendered.append((page_image, figures))
    document.close()
    return rendered
