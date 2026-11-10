"""Layout-agnostic extraction of soil lab parameters from OCR/PDF text.

Does NOT assume a fixed table template. Matches extensible synonym taxonomy
against lines/nearby tokens, supporting comma and dot decimals.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.soil.lab_taxonomy import SOIL_PARAMETER_TAXONOMY, SoilParameterSpec

_VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9])(-?\d{1,4}(?:[.,]\d{1,4})?)(?![A-Za-z0-9])"
)
_UNIT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"mg\s*/\s*100\s*g", "mg/100g"),
    (r"mg\s*/\s*kg", "mg/kg"),
    (r"g\s*/\s*kg", "g/kg"),
    (r"cmol(?:\+|c)?\s*/\s*kg", "cmol/kg"),
    (r"meq\s*/\s*100\s*g", "meq/100g"),
    (r"%", "%"),
    (r"ppm", "ppm"),
)
_METHOD_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bkcl\b", "KCL"),
    (r"\bh\s*2\s*o\b", "H2O"),
    (r"\bh₂o\b", "H2O"),
    (r"\bcacl\s*2\b", "CACL2"),
    (r"\bal\b", "AL"),
    (r"\bolsen\b", "OLSEN"),
)
_DEPTH_RE = re.compile(
    r"(?:dubina|depth)?\s*(\d{1,3})\s*[-–—do]{1,3}\s*(\d{1,3})\s*cm",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedLabParameter:
    parameter_code: str
    original_parameter_name: str
    value: str
    unit: str | None
    method: str | None
    depth_from_cm: Decimal | None
    depth_to_cm: Decimal | None
    extraction_confidence: Decimal
    source_page: int | None
    raw_text: str


@dataclass(frozen=True)
class ExtractionOutcome:
    parameters: list[ExtractedLabParameter]
    laboratory_name: str | None
    analysis_date_hint: str | None
    depth_from_cm: Decimal | None
    depth_to_cm: Decimal | None
    raw_text: str


def extract_lab_parameters_from_text(text: str) -> ExtractionOutcome:
    normalized_full = _fold(text)
    depth_from, depth_to = _detect_depth(normalized_full)
    lab_name = _detect_lab_name(text)
    pages = _split_pages(text)
    found: dict[str, ExtractedLabParameter] = {}

    for page_number, page_text in pages:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            folded = _fold(line)
            for spec in SOIL_PARAMETER_TAXONOMY:
                if spec.code in found and found[spec.code].extraction_confidence >= Decimal("0.85"):
                    continue
                match_name = _match_synonym(folded, spec)
                if not match_name:
                    continue
                same_line_value = _find_value(folded)
                next_line = lines[index + 1] if index + 1 < len(lines) else ""
                # Prefer value on the matched parameter line; only peek one line down if needed.
                value = same_line_value
                value_source = line
                if value is None and next_line:
                    # Avoid stealing the next parameter's value when that line also looks like a param row.
                    if not _line_looks_like_parameter(next_line):
                        value = _find_value(_fold(next_line))
                        value_source = f"{line} | {next_line}"
                if value is None:
                    continue
                unit = _find_unit(_fold(value_source)) or spec.default_unit
                method = _find_method(_fold(value_source)) or _infer_method_from_name(match_name, spec)
                confidence = _score_confidence(
                    synonym_hit=True,
                    value_on_same_line=same_line_value is not None,
                    unit_present=unit is not None,
                    method_present=method is not None,
                )
                candidate = ExtractedLabParameter(
                    parameter_code=spec.code,
                    original_parameter_name=_clip(line, 200),
                    value=value,
                    unit=unit,
                    method=method,
                    depth_from_cm=depth_from,
                    depth_to_cm=depth_to,
                    extraction_confidence=confidence,
                    source_page=page_number,
                    raw_text=_clip(value_source, 400),
                )
                previous = found.get(spec.code)
                if previous is None or candidate.extraction_confidence > previous.extraction_confidence:
                    found[spec.code] = candidate

    return ExtractionOutcome(
        parameters=list(found.values()),
        laboratory_name=lab_name,
        analysis_date_hint=None,
        depth_from_cm=depth_from,
        depth_to_cm=depth_to,
        raw_text=_clip(text, 20000),
    )


def _match_synonym(folded_line: str, spec: SoilParameterSpec) -> str | None:
    for synonym in spec.synonyms:
        token = _fold(synonym)
        if not token:
            continue
        if _synonym_hits(folded_line, token):
            return synonym
    return None


def _synonym_hits(folded_line: str, token: str) -> bool:
    # Short tokens (pH codes, element symbols) need word-ish boundaries to avoid false hits.
    if len(token) <= 3:
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", folded_line) is not None
    return token in folded_line


def _line_looks_like_parameter(line: str) -> bool:
    folded = _fold(line)
    return any(_match_synonym(folded, spec) for spec in SOIL_PARAMETER_TAXONOMY)


def _find_value(folded_line: str) -> str | None:
    # Prefer numbers that look like lab results (not years like 2024, not unit denominators).
    candidates: list[str] = []
    for match in _VALUE_RE.finditer(folded_line):
        raw = match.group(1)
        normalized = raw.replace(",", ".")
        try:
            number = Decimal(normalized)
        except InvalidOperation:
            continue
        if number >= 1900 and number <= 2100 and "." not in normalized:
            continue
        # Skip denominators in units: mg/100g, meq/100 g
        prefix = folded_line[max(0, match.start() - 2) : match.start()]
        if "/" in prefix or prefix.endswith("/"):
            continue
        candidates.append(normalized)
    if not candidates:
        return None
    # Prefer the last numeric token on a parameter line (common table layout).
    return candidates[-1]


def _find_unit(folded: str) -> str | None:
    for pattern, unit in _UNIT_PATTERNS:
        if re.search(pattern, folded, flags=re.IGNORECASE):
            return unit
    return None


def _find_method(folded: str) -> str | None:
    for pattern, method in _METHOD_PATTERNS:
        if re.search(pattern, folded, flags=re.IGNORECASE):
            return method
    return None


def _infer_method_from_name(synonym: str, spec: SoilParameterSpec) -> str | None:
    folded = _fold(synonym)
    for method in spec.methods:
        if _fold(method) in folded:
            return method
    return None


def _detect_depth(folded: str) -> tuple[Decimal | None, Decimal | None]:
    match = _DEPTH_RE.search(folded)
    if not match:
        return None, None
    try:
        return Decimal(match.group(1)), Decimal(match.group(2))
    except InvalidOperation:
        return None, None


def _detect_lab_name(text: str) -> str | None:
    for line in text.splitlines()[:30]:
        cleaned = line.strip()
        folded = _fold(cleaned)
        if any(token in folded for token in ("laborator", "institut", "poljoprivred", "agro")):
            if 4 <= len(cleaned) <= 120:
                return cleaned
    return None


def _score_confidence(
    *,
    synonym_hit: bool,
    value_on_same_line: bool,
    unit_present: bool,
    method_present: bool,
) -> Decimal:
    score = Decimal("0.35")
    if synonym_hit:
        score += Decimal("0.30")
    if value_on_same_line:
        score += Decimal("0.20")
    if unit_present:
        score += Decimal("0.10")
    if method_present:
        score += Decimal("0.05")
    return min(score, Decimal("0.99"))


def _split_pages(text: str) -> list[tuple[int | None, str]]:
    # extract_pdf_pages joins with blank lines; keep single-page fallback.
    if not text.strip():
        return []
    parts = re.split(r"\n\s*\n\s*\n+", text)
    if len(parts) <= 1:
        return [(1, text)]
    return [(index + 1, part) for index, part in enumerate(parts) if part.strip()]


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def _clip(value: str, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
