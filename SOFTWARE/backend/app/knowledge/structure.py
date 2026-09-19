from __future__ import annotations

import re
from dataclasses import dataclass

from app.knowledge.ocr import normalize_ocr_text
from app.knowledge.parse import ParsedPage
from app.knowledge.taxonomy import ManualSpec, fold, heading_catalog


@dataclass
class StructuredPage:
    page_number: int
    raw_text: str
    normalized_text: str
    chapter: str | None
    section: str | None
    subsection: str | None
    domain: str | None
    topic: str | None
    headings: list[str]
    has_text_layer: bool
    ocr_used: bool
    image_png: bytes | None
    embedded_images: list[bytes]


def assign_structure(pages: list[ParsedPage], manual: ManualSpec | None) -> list[StructuredPage]:
    catalog = heading_catalog()
    if manual:
        catalog = [row for row in catalog if row[1] == manual.key]
    toc_pages = {page.page_number for page in pages[:5] if len(_headings_on_page(page.raw_text, catalog, manual)) >= 4}
    toc_map = _toc_page_map(pages, catalog, manual, toc_pages)

    current_chapter = manual.sections[0] if manual and manual.sections else None
    current_section = current_chapter
    current_subsection = None
    current_domain = manual.domain if manual else None
    current_topic = None
    structured: list[StructuredPage] = []
    for page in pages:
        normalized = normalize_ocr_text(page.raw_text)
        found = _headings_on_page(normalized, catalog, manual)
        headings = [item[0] for item in found]
        toc_hit = toc_map.get(page.page_number)
        fingerprint = _fingerprint_section(normalized)
        if page.page_number not in toc_pages and 0 < len(found) <= 3:
            heading, _doc, domain, topic = found[0]
            current_section = heading
            current_topic = topic
            current_domain = domain
            if _is_chapter(heading, manual):
                current_chapter = heading
        elif fingerprint:
            heading, domain, topic, chapter = fingerprint
            current_section = heading
            current_domain = domain
            current_topic = topic
            if chapter:
                current_chapter = chapter
        elif toc_hit:
            heading, domain, topic, chapter = toc_hit
            current_section = heading
            current_domain = domain
            current_topic = topic
            current_chapter = chapter or current_chapter
        structured.append(
            StructuredPage(
                page_number=page.page_number,
                raw_text=page.raw_text,
                normalized_text=normalized,
                chapter=current_chapter,
                section=current_section or current_chapter,
                subsection=current_subsection,
                domain=current_domain,
                topic=current_topic,
                headings=headings,
                has_text_layer=page.has_text_layer,
                ocr_used=page.ocr_used,
                image_png=page.image_png,
                embedded_images=page.embedded_images,
            )
        )
    return structured


def _is_chapter(heading: str, manual: ManualSpec | None) -> bool:
    if manual is None:
        return False
    top = {
        "Osnovna hraniva i njihova uloga u uzgoju leske",
        "Đubrenje",
        "Analiza zemljišta i klime",
        "Zasnovanje voćnjaka",
        "Održavanje voćnjaka",
        "Štetne vrste insekata i bolesti",
        "Štete nastale uticajem ekstremnih vremenskih uslova",
        "Dobra praksa",
        "Kalendar zaštite",
    }
    return heading in top


def _headings_on_page(
    text: str,
    catalog: list[tuple[str, str, str, str]],
    manual: ManualSpec | None,
) -> list[tuple[str, str, str, str]]:
    folded = fold(text)
    compact = re.sub(r"[^a-z0-9]+", "", folded)
    found: list[tuple] = []
    for heading, doc_key, domain, topic in catalog:
        if manual and doc_key != manual.key:
            continue
        if _heading_matches(heading, folded, compact):
            pos = folded.find(fold(heading))
            found.append((pos if pos >= 0 else 10_000, heading, doc_key, domain, topic))
    found.sort(key=lambda item: (item[0], -len(item[1])))
    return [(heading, doc_key, domain, topic) for _pos, heading, doc_key, domain, topic in found]


def _heading_matches(heading: str, folded_page: str, compact_page: str) -> bool:
    needle = fold(heading)
    if 4 <= len(needle) <= 5:
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", folded_page) is not None
    if len(needle) >= 6 and needle in folded_page:
        return True
    compact_needle = re.sub(r"[^a-z0-9]+", "", needle)
    if len(compact_needle) >= 10 and compact_needle in compact_page:
        return True
    tokens = [token for token in needle.split() if len(token) >= 5]
    return len(tokens) >= 2 and all(token in folded_page for token in tokens)


def _toc_page_map(
    pages: list[ParsedPage],
    catalog: list[tuple[str, str, str, str]],
    manual: ManualSpec | None,
    toc_pages: set[int],
) -> dict[int, tuple[str, str, str, str | None]]:
    blob = "\n".join(page.raw_text or "" for page in pages[:5])
    compact_blob = re.sub(r"[^a-z0-9]+", "", fold(blob))
    entries: list[tuple[int, str, str, str, str | None]] = []
    for heading, doc_key, domain, topic in catalog:
        if manual and doc_key != manual.key:
            continue
        printed = _heading_printed_page(heading, compact_blob)
        if printed is None:
            continue
        chapter = heading if _is_chapter(heading, manual) else None
        entries.append((printed, heading, domain, topic, chapter))
    entries = _sanitize_toc(entries)
    if not entries:
        return {}
    offset = _detect_offset(pages, entries, toc_pages)
    last_page = pages[-1].page_number if pages else entries[-1][0]
    by_pdf: dict[int, tuple[str, str, str, str | None]] = {}
    current_chapter = manual.sections[0] if manual and manual.sections else None
    for index, (printed, heading, domain, topic, chapter) in enumerate(entries):
        start = max(1, min(last_page, printed + offset))
        if index + 1 < len(entries):
            end = max(start, entries[index + 1][0] + offset - 1)
        else:
            end = last_page
        if chapter:
            current_chapter = chapter
        for page_number in range(start, end + 1):
            by_pdf[page_number] = (heading, domain, topic, current_chapter)
    return by_pdf


def _heading_printed_page(heading: str, compact_blob: str) -> int | None:
    compact = re.sub(r"[^a-z0-9]+", "", fold(heading))
    if len(compact) < 8:
        compact = re.sub(r"[^a-z0-9]+", "", fold(heading))
        if len(compact) < 4:
            return None
    idx = compact_blob.find(compact)
    if idx < 0:
        return None
    rest = compact_blob[idx + len(compact) : idx + len(compact) + 2]
    match = re.match(r"(\d{1,2})", rest)
    if not match:
        return None
    number = int(match.group(1))
    if 1 <= number <= 200:
        return number
    return None


def _sanitize_toc(entries: list[tuple[int, str, str, str, str | None]]) -> list[tuple[int, str, str, str, str | None]]:
    unique: dict[str, tuple[int, str, str, str, str | None]] = {}
    for item in entries:
        heading = item[1]
        if heading not in unique or item[0] < unique[heading][0]:
            unique[heading] = item
    ordered = sorted(unique.values(), key=lambda item: item[0])
    cleaned: list[tuple[int, str, str, str, str | None]] = []
    for item in ordered:
        number = item[0]
        if number >= 90 and cleaned and number - cleaned[-1][0] > 40:
            continue
        if cleaned and number < cleaned[-1][0]:
            continue
        cleaned.append(item)
    return cleaned


def _detect_offset(
    pages: list[ParsedPage],
    entries: list[tuple[int, str, str, str, str | None]],
    toc_pages: set[int],
) -> int:
    by_number = {page.page_number: page for page in pages}
    best_offset = 0
    best_score = -1
    for offset in range(-6, 3):
        score = 0
        for printed, heading, _domain, _topic, _chapter in entries:
            pdf_page = printed + offset
            page = by_number.get(pdf_page)
            if page is None or pdf_page in toc_pages:
                continue
            folded = fold(page.raw_text)
            compact = re.sub(r"[^a-z0-9]+", "", folded)
            if _heading_matches(heading, folded, compact):
                score += 2
            else:
                tokens = [token for token in fold(heading).split() if len(token) >= 5]
                if tokens and sum(1 for token in tokens if token in folded) >= max(1, len(tokens) - 1):
                    score += 1
        if score > best_score:
            best_score = score
            best_offset = offset
    return best_offset


def _fingerprint_section(text: str) -> tuple[str, str, str, str | None] | None:
    folded = fold(text)
    rules = (
        ("mikroelementi su neophodni", "Mikroelementi", "nutrition", "microelements", "Osnovna hraniva i njihova uloga u uzgoju leske"),
        ("tabela 12", "Mikroelementi", "nutrition", "microelements", "Osnovna hraniva i njihova uloga u uzgoju leske"),
        ("prolecni mrazevi", "Mraz", "environmental_damage", "frost", "Štete nastale uticajem ekstremnih vremenskih uslova"),
        ("izazvana olujom i gra", "Grad", "environmental_damage", "hail", "Štete nastale uticajem ekstremnih vremenskih uslova"),
        ("pragovima tole", "Kalendar zaštite", "protection_calendar", "productive_trees", "Kalendar zaštite"),
        ("orijentaci", "Kalendar zaštite", "protection_calendar", "productive_trees", "Kalendar zaštite"),
        ("zastita mladih zasada", "Za mlada stabla", "protection_calendar", "young_trees", "Kalendar zaštite"),
        ("zastita zasada u rodu", "Za stabla u rodu", "protection_calendar", "productive_trees", "Kalendar zaštite"),
        ("dobra proizvodna praksa", "Dobra praksa", "good_practice", "good_practice", "Dobra praksa"),
    )
    for needle, heading, domain, topic, chapter in rules:
        if needle in folded:
            return heading, domain, topic, chapter
    return None


def detect_content_types(text: str) -> list[str]:
    types = ["text"]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tableish = 0
    for line in lines:
        separators = len(re.findall(r"\s{2,}|\||;", line))
        if separators >= 2 and len(line) < 160:
            tableish += 1
    if tableish >= 3:
        types.append("table")
    if re.search(r"\d+\s*(kg/ha|g/m|%|ppm|l/ha)", text, re.IGNORECASE) and re.search(r"[=×x]\s*\d", text):
        types.append("formula")
    return types
