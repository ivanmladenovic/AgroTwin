"""Deterministic calculations for parcel annual reports. No I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

ChangeDirection = Literal["up", "down", "unchanged"]
ChangeTone = Literal["positive", "negative", "neutral"]
MetricSemantics = Literal["higher_better", "lower_better", "neutral"]

MONEY_UNITS = {"eur", "euro", "€"}
MASS_UNIT_TO_KG: dict[str, Decimal] = {
    "kg": Decimal("1"),
    "g": Decimal("0.001"),
    "t": Decimal("1000"),
    "ton": Decimal("1000"),
    "tona": Decimal("1000"),
    "tone": Decimal("1000"),
}

TIMELINE_PRIORITY = {
    "harvesting": 0,
    "pruning": 1,
    "spraying": 2,
    "fertilization": 3,
    "irrigation": 4,
    "planting": 5,
    "disease_treatment": 6,
    "maintenance": 7,
    "inspection": 8,
    "soil_analysis": 9,
}

METRIC_SEMANTICS: dict[str, MetricSemantics] = {
    "yield_kg": "higher_better",
    "attention_trees": "lower_better",
    "problem_cases": "lower_better",
    "annual_cost": "neutral",
    "activities_completed": "neutral",
    "activities_planned": "neutral",
    "total_trees": "neutral",
    "healthy_trees": "higher_better",
    "cost_per_hectare": "neutral",
    "cost_per_tree": "neutral",
    "cost_per_kg": "lower_better",
}


def year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def as_decimal(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def percent_change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.1"))


def change_direction(current: Decimal | None, previous: Decimal | None) -> ChangeDirection | None:
    if current is None or previous is None:
        return None
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "unchanged"


def change_tone(metric_key: str, direction: ChangeDirection | None) -> ChangeTone | None:
    if direction is None:
        return None
    if direction == "unchanged":
        return "neutral"
    semantics = METRIC_SEMANTICS.get(metric_key, "neutral")
    if semantics == "neutral":
        return "neutral"
    improved = (semantics == "higher_better" and direction == "up") or (
        semantics == "lower_better" and direction == "down"
    )
    return "positive" if improved else "negative"


def is_money_unit(unit: str | None) -> bool:
    return (unit or "").strip().lower().replace("€", "eur") in MONEY_UNITS


def yield_kg_from_line_items(items: list[dict] | None, quantity: Decimal | None = None, unit: str | None = None) -> Decimal | None:
    total = Decimal("0")
    found = False
    for item in items or []:
        kg = mass_to_kg(item.get("quantity"), item.get("unit"))
        if kg is None:
            continue
        total += kg
        found = True
    if not found:
        kg = mass_to_kg(quantity, unit)
        if kg is None:
            return None
        return kg
    return total


def mass_to_kg(quantity: Decimal | int | float | str | None, unit: str | None) -> Decimal | None:
    if quantity is None or quantity == "":
        return None
    if is_money_unit(unit):
        return None
    factor = MASS_UNIT_TO_KG.get((unit or "").strip().lower())
    if factor is None:
        return None
    return Decimal(str(quantity)) * factor


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal("0.01"))
    sign = "-" if quantized < 0 else ""
    absolute = abs(quantized)
    whole = int(absolute)
    cents = int((absolute - whole) * 100)
    grouped = f"{whole:,}".replace(",", ".")
    if cents:
        return f"{sign}{grouped},{cents:02d} €"
    return f"{sign}{grouped} €"


def format_kg(value: Decimal | None) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral():
        return f"{int(quantized):,}".replace(",", ".") + " kg"
    text = f"{quantized:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} kg"


def timeline_rank(slug: str | None) -> int:
    return TIMELINE_PRIORITY.get(slug or "", 50)


def pick_monthly_highlights(activities: list[dict]) -> list[dict]:
    """Keep one notable completed activity per month, earliest among the highest-priority type."""
    by_month: dict[int, dict] = {}
    for item in activities:
        performed = item["performed_on"]
        month = performed.month if isinstance(performed, date) else int(str(performed)[5:7])
        current = by_month.get(month)
        if current is None:
            by_month[month] = item
            continue
        item_rank = timeline_rank(item.get("slug"))
        current_rank = timeline_rank(current.get("slug"))
        if item_rank < current_rank:
            by_month[month] = item
            continue
        if item_rank == current_rank and item["performed_on"] < current["performed_on"]:
            by_month[month] = item
    return [by_month[month] for month in sorted(by_month)]


def ratio(numerator: Decimal | None, denominator: Decimal | int | None) -> Decimal | None:
    if numerator is None or denominator is None:
        return None
    denom = Decimal(str(denominator))
    if denom <= 0:
        return None
    return (numerator / denom).quantize(Decimal("0.01"))


def build_executive_summary(
    *,
    year: int,
    previous_year: int,
    parcel_name: str,
    activities_completed: int,
    annual_cost: Decimal | None,
    costs_available: bool,
    yield_kg: Decimal | None,
    yield_change_percent: Decimal | None,
    attention_count: int,
    top_problem_row: int | None,
) -> str:
    parts: list[str] = []
    cost_text = money(annual_cost) if costs_available and annual_cost is not None else None
    if cost_text:
        parts.append(
            f"Tokom {year}. godine parcela {parcel_name} je imala {activities_completed} urađenih aktivnosti "
            f"i ukupan trošak od {cost_text}."
        )
    else:
        parts.append(
            f"Tokom {year}. godine parcela {parcel_name} je imala {activities_completed} urađenih aktivnosti."
        )

    if yield_kg is not None and yield_change_percent is not None:
        if yield_change_percent > 0:
            parts.append(f"Prinos je porastao za {yield_change_percent}% u odnosu na {previous_year}.")
        elif yield_change_percent < 0:
            parts.append(f"Prinos je pao za {abs(yield_change_percent)}% u odnosu na {previous_year}.")
        else:
            parts.append(f"Prinos je ostao na nivou {previous_year}. ({format_kg(yield_kg)}).")
    elif yield_kg is not None:
        parts.append(f"Zabeležen prinos iznosi {format_kg(yield_kg)}.")

    attention = (
        f"{attention_count} stabala trenutno zahteva pažnju"
        if attention_count != 1
        else "1 stablo trenutno zahteva pažnju"
    )
    if top_problem_row is not None:
        attention += f", sa najvećom koncentracijom problema u redu {top_problem_row}."
    else:
        attention += "."
    parts.append(attention)
    return " ".join(parts)
