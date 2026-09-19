from __future__ import annotations

import re
from io import BytesIO


def build_text_pdf(title: str, sections: list[tuple[str, str]]) -> bytes:
    """Minimal multi-page PDF used for demo knowledge documents."""

    pages: list[list[str]] = []
    current: list[str] = [title, ""]
    for heading, body in sections:
        block = [heading, ""] + _wrap(body, 90) + [""]
        if len(current) + len(block) > 42 and current:
            pages.append(current)
            current = []
        current.extend(block)
    if current:
        pages.append(current)
    return _write_pdf(pages)


def extract_pdf_pages(content: bytes) -> list[tuple[int, str]]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((index, text))
    return pages


def chunk_pages(
    pages: list[tuple[int, str]],
    *,
    size: int = 900,
    overlap: int = 140,
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    index = 0
    for page_number, text in pages:
        section = _guess_section(text)
        start = 0
        cleaned = re.sub(r"\s+", " ", text).strip()
        while start < len(cleaned):
            piece = cleaned[start : start + size].strip()
            if piece:
                chunks.append(
                    {
                        "chunk_index": index,
                        "page_number": page_number,
                        "section_title": section,
                        "content": piece,
                        "token_count": len(piece.split()),
                    }
                )
                index += 1
            if start + size >= len(cleaned):
                break
            start += size - overlap
    return chunks


def _guess_section(text: str) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if 8 <= len(candidate) <= 80 and (candidate.isupper() or candidate.istitle()):
            return candidate[:255]
    return None


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) > width:
            if current:
                lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


def _write_pdf(pages: list[list[str]]) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"__PAGES__",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content_ids: list[int] = []
    page_ids: list[int] = []
    for lines in pages:
        safe = [_pdf_escape(line[:110]) for line in lines[:46]]
        stream = "BT /F1 11 Tf 50 780 Td\n" + "\n".join(f"({line}) Tj 0 -16 Td" for line in safe) + "\nET"
        stream_bytes = stream.encode("latin-1", "replace")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream_bytes) + stream_bytes + b"\nendstream")
        content_ids.append(len(objects))
        objects.append(b"__PAGE__")
        page_ids.append(len(objects))

    kids = " ".join(f"{item} 0 R" for item in page_ids)
    objects[1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode()
    for page_id, content_id in zip(page_ids, content_ids, strict=True):
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode()

    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{index} 0 obj\n".encode())
        body.extend(obj)
        body.extend(b"\nendobj\n")
    xref = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(body)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
