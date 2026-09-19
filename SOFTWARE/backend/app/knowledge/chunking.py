from __future__ import annotations

import re
from typing import Any

from app.knowledge.structure import StructuredPage, detect_content_types

TARGET_CHARS = 1800
OVERLAP_CHARS = 220


def chunk_structured_pages(pages: list[StructuredPage], document_title: str) -> list[dict[str, Any]]:
    """Structure-aware chunks: keep a section together when short, split long ones."""
    groups: list[list[StructuredPage]] = []
    current: list[StructuredPage] = []
    current_key: tuple[str | None, str | None] | None = None
    for page in pages:
        if not (page.normalized_text or "").strip():
            continue
        key = (page.chapter, page.section)
        if current and key != current_key:
            groups.append(current)
            current = []
        current.append(page)
        current_key = key
    if current:
        groups.append(current)

    chunks: list[dict[str, Any]] = []
    index = 0
    for group in groups:
        buffer_pages: list[StructuredPage] = []
        buffer_parts: list[str] = []
        for page in group:
            text = (page.normalized_text or "").strip()
            if not text:
                continue
            joined = "\n\n".join([*buffer_parts, text]) if buffer_parts else text
            if buffer_pages and len(joined) > TARGET_CHARS:
                index = _append_text_chunks(chunks, index, buffer_pages, "\n\n".join(buffer_parts), document_title)
                buffer_pages = [page]
                buffer_parts = [text]
            else:
                buffer_pages.append(page)
                buffer_parts.append(text)
        if buffer_pages:
            index = _append_text_chunks(chunks, index, buffer_pages, "\n\n".join(buffer_parts), document_title)
        for page in group:
            if page.image_png or page.embedded_images:
                context = page.normalized_text[:400]
                chunks.append(
                    {
                        "chunk_index": index,
                        "page_number": page.page_number,
                        "page_end": page.page_number,
                        "chapter": page.chapter,
                        "section_title": page.section,
                        "subsection": page.subsection,
                        "domain": page.domain,
                        "topic": page.topic,
                        "content_type": "image",
                        "raw_text": context,
                        "content": context or f"Slika sa strane {page.page_number}",
                        "token_count": len((context or "").split()),
                        "language": "sr",
                        "extra": {"has_page_image": bool(page.image_png), "embedded_count": len(page.embedded_images)},
                        "document_title": document_title,
                    }
                )
                index += 1
    return chunks


def _append_text_chunks(
    chunks: list[dict[str, Any]],
    index: int,
    pages: list[StructuredPage],
    text: str,
    document_title: str,
) -> int:
    first = pages[0]
    last = pages[-1]
    types = detect_content_types(text)
    pieces = _split_text(text) if len(text) > TARGET_CHARS + 400 else [text]
    for piece in pieces:
        content_type = "table" if "table" in types and _looks_like_table(piece) else "text"
        if "formula" in types and _looks_like_formula(piece):
            content_type = "formula"
        extra: dict[str, Any] = {}
        if content_type == "table":
            extra["markdown"] = piece
            extra["uncertain"] = True
        if content_type == "formula":
            extra["uncertain"] = True
        chunks.append(
            {
                "chunk_index": index,
                "page_number": first.page_number,
                "page_end": last.page_number,
                "chapter": first.chapter,
                "section_title": first.section,
                "subsection": first.subsection,
                "domain": first.domain,
                "topic": first.topic,
                "content_type": content_type,
                "raw_text": piece,
                "content": piece,
                "token_count": len(piece.split()),
                "language": "sr",
                "extra": extra,
                "document_title": document_title,
            }
        )
        index += 1
    return index


def _split_text(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    buf = ""
    for paragraph in paragraphs:
        candidate = f"{buf}\n\n{paragraph}".strip() if buf else paragraph.strip()
        if len(candidate) <= TARGET_CHARS:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(paragraph) <= TARGET_CHARS:
            buf = paragraph.strip()
        else:
            start = 0
            while start < len(paragraph):
                end = min(len(paragraph), start + TARGET_CHARS)
                chunks.append(paragraph[start:end].strip())
                start = max(end - OVERLAP_CHARS, end)
            buf = ""
    if buf:
        chunks.append(buf)
    return [item for item in chunks if item]


def _looks_like_table(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    spaced = sum(1 for line in lines if len(re.findall(r"\s{2,}", line)) >= 2)
    return spaced >= 3


def _looks_like_formula(text: str) -> bool:
    return bool(re.search(r"\d+.*=.*\d+", text) or re.search(r"\d+\s*kg/ha", text, re.IGNORECASE))
