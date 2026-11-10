"""Shared display formatting for compliance PDF/CSV/JSON tables."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


FILTER_LABELS: dict[str, str] = {
    "date_from": "Od datuma",
    "date_to": "Do datuma",
    "parcel_ids": "Parcele",
    "include_costs": "Uključi troškove",
    "report_types": "Tipovi izveštaja",
    "farm_id": "Gazdinstvo",
    "crop": "Kultura",
    "product": "Preparat / proizvod",
    "active_substance": "Aktivna materija",
    "operator": "Izvršilac",
    "activity_type_id": "Tip aktivnosti",
    "worker_id": "Radnik",
}

BOOL_SR = {True: "Da", False: "Ne", "yes": "Da", "no": "Ne", "true": "Da", "false": "Ne"}

VALUE_LABELS: dict[str, str] = {
    "conventional": "Konvencionalna",
    "organic": "Organska",
    "none": "Nema",
    "entire_parcel": "Cela parcela",
    "part_of_parcel": "Deo parcele",
    "drip": "Kap po kap",
    "sprinkler": "Prskalice",
    "microsprinkler": "Mikroprskalice",
    "other": "Ostalo",
    "fertilizer": "Đubrivo",
    "parcel_profile": "Profil parcele",
    "activity": "Aktivnost",
    "no_lot": "Bez lota",
    "draft": "Nacrt",
    "published": "Objavljen",
    "archived": "Arhiviran",
}


def format_date(value: date | datetime | str | None) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y.")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y.")
    text = str(value).strip()
    if not text:
        return ""
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d.%m.%Y.")
        return date.fromisoformat(text[:10]).strftime("%d.%m.%Y.")
    except ValueError:
        return text


def format_datetime(value: datetime | str | None) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    local = value
    if local.tzinfo is not None:
        local = local.astimezone()
    return local.strftime("%d.%m.%Y. %H:%M")


def format_money_eur(value: Decimal | float | int | str | None) -> str:
    if value is None or value == "":
        return ""
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} EUR"


def format_quantity(value: Decimal | float | int | str | None) -> str:
    if value is None or value == "":
        return ""
    text = str(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_display_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return BOOL_SR[value]
    if isinstance(value, (date, datetime)):
        return format_date(value)
    text = str(value)
    lowered = text.lower()
    if lowered in BOOL_SR:
        return BOOL_SR[lowered]
    if lowered in VALUE_LABELS:
        return VALUE_LABELS[lowered]
    return text


def format_filters(filters: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in filters.items():
        if value in (None, "", [], {}):
            continue
        label = FILTER_LABELS.get(key, key)
        if key in {"date_from", "date_to"}:
            parts.append(f"{label}: {format_date(value)}")
        elif key == "include_costs":
            parts.append(f"{label}: {BOOL_SR.get(bool(value), str(value))}")
        elif key == "report_types":
            if isinstance(value, list):
                parts.append(f"{label}: {', '.join(str(item) for item in value)}")
            else:
                parts.append(f"{label}: {value}")
        elif key == "parcel_ids":
            count = len(value) if isinstance(value, list) else 1
            parts.append(f"{label}: {count}")
        else:
            parts.append(f"{label}: {value}")
    return "; ".join(parts) if parts else "bez dodatnih filtera"
