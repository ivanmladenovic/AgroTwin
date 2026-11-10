"""Read a laboratory soil report with the AI model.

Does not call OCR. Missing values stay absent; they are never filled with zero.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from app.ai.base import ChatMessage
from app.soil.lab_taxonomy import TAXONOMY_BY_CODE

logger = logging.getLogger(__name__)

KEY_PARAMETER_CODES = (
    "PH",
    "HUMUS",
    "ORGANIC_CARBON",
    "TOTAL_N",
    "AVAILABLE_P",
    "AVAILABLE_K",
    "CA",
    "MG",
    "TEXTURE",
    "CEC",
    "S",
    "FE",
    "ZN",
    "B",
    "MN",
    "CU",
)

MAX_VISION_PAGES = 3


def render_document_images(payload: bytes, content_type: str | None) -> list[tuple[bytes, str]]:
    """First pages of a PDF, or the image itself. Empty when the file cannot be rendered."""
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime.startswith("image/"):
        return [(payload, mime or "image/jpeg")]
    if not payload.startswith(b"%PDF") and mime not in {"application/pdf", "application/x-pdf"}:
        return []
    try:
        import fitz
    except ImportError:
        return []
    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        return []
    pages: list[tuple[bytes, str]] = []
    try:
        for page in list(document)[:MAX_VISION_PAGES]:
            jpeg = _page_jpeg(page)
            if jpeg:
                pages.append((jpeg, "image/jpeg"))
    finally:
        document.close()
    return pages


def read_lab_document(provider: Any, payload: bytes, content_type: str | None) -> dict[str, Any]:
    """Ask the model for the key parameters visible on the report."""
    # Digital PDFs already have a text layer. Send that text; do not render pages.
    # Scans have almost no text, so the model sees small page images instead. No OCR.
    report_text = _pdf_text_layer(payload, content_type)
    images = [] if len(report_text) >= 80 else render_document_images(payload, content_type)
    if not report_text and not images:
        return _empty_reading("Dokument nije mogao da se prikaže modelu.")
    prompt = _reading_prompt(report_text if len(report_text) >= 80 else None)
    user_content: str | list[dict] = prompt
    if images:
        import base64

        parts: list[dict] = [{"type": "text", "text": prompt}]
        for image, mime in images:
            encoded = base64.b64encode(image).decode("ascii")
            parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}})
        user_content = parts
    try:
        result = provider.chat(
            [
                ChatMessage(
                    role="system",
                    content="Čitaš laboratorijski izveštaj. Odgovaraš isključivo JSON-om. Ne izmišljaš brojeve.",
                ),
                ChatMessage(role="user", content=user_content),
            ],
            tools=None,
            json_mode=True,
            temperature=0.0,
            # Page images of a scan are large. The dedicated vision model timed out
            # on them; the smaller chat model read the same report.
            model=getattr(provider, "chat_model", None) if images else None,
        )
    except Exception:
        logger.exception("Soil lab vision read failed")
        return _empty_reading("Model nije uspeo da pročita analizu.")
    reading = parse_lab_reading(result.content or "")
    if not reading["parameters"] and not reading["summary"]:
        reading["error"] = "Model nije vratio parametre sa izveštaja."
    return reading


def parse_lab_reading(raw: str) -> dict[str, Any]:
    payload = _json_object(raw)
    parameters: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for item in payload.get("parameters") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().upper()
        if code not in TAXONOMY_BY_CODE or code in seen:
            continue
        value = _clean_value(item.get("value"))
        if value is None:
            continue
        seen.add(code)
        spec = TAXONOMY_BY_CODE[code]
        name = _clean_text(item.get("name")) or spec.label
        parameters.append(
            {
                "code": code,
                "name": name[:512],
                "value": value[:128],
                "unit": _clean_text(item.get("unit")) or spec.default_unit,
                "method": _clean_text(item.get("method")),
            }
        )
    sampled = _clean_text(payload.get("sampled_on"))
    if sampled:
        try:
            date.fromisoformat(sampled[:10])
            sampled = sampled[:10]
        except ValueError:
            sampled = None
    return {
        "laboratory_name": _clean_text(payload.get("laboratory_name")),
        "sampled_on": sampled,
        "summary": _clean_text(payload.get("summary")),
        "parameters": parameters,
        "error": None,
    }


def format_lab_reading(reading: dict[str, Any] | None) -> str | None:
    if not reading:
        return None
    lines: list[str] = []
    summary = _clean_text(reading.get("summary"))
    if summary:
        lines.append(summary)
    for item in reading.get("parameters") or []:
        if not isinstance(item, dict) or not item.get("value"):
            continue
        unit = f" {item['unit']}" if item.get("unit") else ""
        method = f" ({item['method']})" if item.get("method") else ""
        lines.append(f"- {item.get('name') or item.get('code')}: {item.get('value')}{unit}{method}")
    if not lines:
        return None
    return "\n".join(lines)


def remembered_lab_block(messages: list[Any]) -> str | None:
    """Readings already stored on earlier chat messages. One block, not one per index."""
    chunks: list[str] = []
    seen: set[str] = set()
    for message in messages:
        for ref in getattr(message, "structured_refs", None) or []:
            if not isinstance(ref, dict):
                continue
            reading = (ref.get("extra") or {}).get("lab_reading")
            rendered = format_lab_reading(reading if isinstance(reading, dict) else None)
            if not rendered or rendered in seen:
                continue
            seen.add(rendered)
            label = ref.get("label") or "analiza"
            chunks.append(f"Dokument: {label}\n{rendered}")
    if not chunks:
        return None
    return (
        "SAČUVANA LABORATORIJSKA ANALIZA IZ OVOG RAZGOVORA "
        "(već pročitana; ne tražite ponovo upload i ne recite da je nemate):\n"
        + "\n\n".join(chunks)
    )


def _reading_prompt(report_text: str | None) -> str:
    codes = ", ".join(
        f"{code} ({TAXONOMY_BY_CODE[code].label})"
        for code in KEY_PARAMETER_CODES
        if code in TAXONOMY_BY_CODE
    )
    prompt = (
        "Ovo je laboratorijska analiza zemljišta. Pročitaj izveštaj i vrati samo JSON.\n"
        "Uključi samo vrednosti koje su zaista napisane. Ako parametra nema, izostavi ga. "
        "Ne pretvaraj prazno polje u nulu.\n"
        f"Najbitniji kodovi: {codes}.\n"
        "Oblik:\n"
        '{"laboratory_name": null, "sampled_on": null, "summary": "", '
        '"parameters": [{"code": "PH", "name": "pH", "value": "6.8", "unit": null, "method": null}]}\n'
        "sampled_on je YYYY-MM-DD ili null. summary je 2-4 rečenice na srpskom, "
        "samo o pročitanim parametrima, bez preporuke đubrenja i bez tvrdnje da je dijagnoza."
    )
    if report_text:
        prompt += f"\n\nTEKST IZVEŠTAJA:\n{report_text[:12000]}"
    return prompt


def _pdf_text_layer(payload: bytes, content_type: str | None) -> str:
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime.startswith("image/") or not payload:
        return ""
    if not payload.startswith(b"%PDF") and mime not in {"application/pdf", "application/x-pdf"}:
        return ""
    try:
        from app.knowledge.pdf import extract_pdf_pages

        pages = extract_pdf_pages(payload)
    except Exception:
        return ""
    return "\n\n".join(text for _, text in pages if text).strip()


def _page_jpeg(page: Any) -> bytes | None:
    """Keep each page small enough that the vision request returns instead of timing out."""
    rect = page.rect
    longest = max(float(rect.width), float(rect.height)) or 1.0
    scale = min(1.3, 1100.0 / longest)
    pixmap = page.get_pixmap(matrix=_matrix(scale), alpha=False)
    jpeg = pixmap.tobytes("jpeg", jpg_quality=60)
    if len(jpeg) > 700_000:
        pixmap = page.get_pixmap(matrix=_matrix(scale * 0.65), alpha=False)
        jpeg = pixmap.tobytes("jpeg", jpg_quality=45)
    if not jpeg or len(jpeg) > 900_000:
        return None
    return jpeg


def _matrix(scale: float) -> Any:
    import fitz

    return fitz.Matrix(scale, scale)


def _empty_reading(error: str) -> dict[str, Any]:
    return {
        "laboratory_name": None,
        "sampled_on": None,
        "summary": None,
        "parameters": [],
        "error": error,
    }


def _json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a", "-", "—"}:
        return None
    return text


def _clean_value(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text in {"0", "0.0", "0,0"} and not re.search(r"[1-9]", text):
        # A literal zero can be a real lab result (rare). Keep it only when the
        # model sent a unit-bearing or explicit measurement, which _clean_text already kept.
        return text
    return text
