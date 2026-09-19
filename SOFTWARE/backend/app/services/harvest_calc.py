"""Deterministic harvest and yield calculations. No I/O."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from app.models.enums import HarvestQualityCategory, ScopeType
from app.services.parcel_report_calc import mass_to_kg, percent_change, ratio, year_bounds

PARCEL_TOTAL_NOTE = (
    "Ukupan prinos parcele računa se samo iz berbi na nivou parcele. "
    "Berbe redova i stabala su posebna merenja i ne sabiraju se sa prinosom parcele."
)

MISSING_PREVIOUS_YEAR = "Nema podataka o berbi za prethodnu godinu."


@dataclass(frozen=True)
class HarvestMeasure:
    scope_type: str
    harvested_on: date
    gross: Decimal
    loss: Decimal
    unit: str = "kg"
    moisture_percent: Decimal | None = None
    damaged_percent: Decimal | None = None
    empty_nuts_percent: Decimal | None = None
    foreign_material_percent: Decimal | None = None
    quality_category: HarvestQualityCategory | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None

    @property
    def net(self) -> Decimal:
        return net_quantity(self.gross, self.loss)


def net_quantity(gross: Decimal, loss: Decimal | None = None) -> Decimal:
    waste = loss if loss is not None else Decimal("0")
    return gross - waste


def validate_quantities(gross: Decimal, loss: Decimal | None = None) -> Decimal:
    waste = loss if loss is not None else Decimal("0")
    if gross <= 0:
        raise ValueError("Bruto količina mora biti veća od nule.")
    if waste < 0:
        raise ValueError("Gubitak ne može biti negativan.")
    if waste > gross:
        raise ValueError("Gubitak ne može biti veći od bruto količine.")
    return net_quantity(gross, waste)


def quantity_kg(quantity: Decimal | int | float | str | None, unit: str | None) -> Decimal | None:
    return mass_to_kg(quantity, unit or "kg")


def parcel_scope_only(items: Iterable[HarvestMeasure]) -> list[HarvestMeasure]:
    return [item for item in items if item.scope_type == ScopeType.PARCEL.value or item.scope_type == "parcel"]


def total_kg(items: Iterable[HarvestMeasure], field: str = "net") -> Decimal | None:
    records = list(items)
    if not records:
        return None
    total = Decimal("0")
    found = False
    for item in records:
        value = item.net if field == "net" else item.gross if field == "gross" else item.loss
        kg = quantity_kg(value, item.unit)
        if kg is None:
            continue
        total += kg
        found = True
    return total if found else None


def first_last_dates(items: Iterable[HarvestMeasure]) -> tuple[date | None, date | None]:
    dates = [item.harvested_on for item in items]
    if not dates:
        return None, None
    return min(dates), max(dates)


def timeline_points(items: Iterable[HarvestMeasure]) -> list[dict]:
    grouped: dict[date, dict[str, Decimal | int]] = {}
    for item in items:
        net = quantity_kg(item.net, item.unit)
        gross = quantity_kg(item.gross, item.unit)
        loss = quantity_kg(item.loss, item.unit)
        if net is None:
            continue
        bucket = grouped.setdefault(
            item.harvested_on,
            {"event_count": 0, "gross_kg": Decimal("0"), "loss_kg": Decimal("0"), "net_kg": Decimal("0")},
        )
        bucket["event_count"] = int(bucket["event_count"]) + 1
        bucket["gross_kg"] = Decimal(str(bucket["gross_kg"])) + (gross or Decimal("0"))
        bucket["loss_kg"] = Decimal(str(bucket["loss_kg"])) + (loss or Decimal("0"))
        bucket["net_kg"] = Decimal(str(bucket["net_kg"])) + net
    points: list[dict] = []
    cumulative = Decimal("0")
    for harvested_on in sorted(grouped):
        bucket = grouped[harvested_on]
        cumulative += Decimal(str(bucket["net_kg"]))
        points.append(
            {
                "harvested_on": harvested_on,
                "event_count": int(bucket["event_count"]),
                "gross_kg": Decimal(str(bucket["gross_kg"])),
                "loss_kg": Decimal(str(bucket["loss_kg"])),
                "net_kg": Decimal(str(bucket["net_kg"])),
                "cumulative_net_kg": cumulative,
            }
        )
    return points


def weighted_average(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    usable = [(value, weight) for value, weight in pairs if weight > 0]
    if not usable:
        return None
    total_weight = sum((weight for _value, weight in usable), Decimal("0"))
    if total_weight <= 0:
        return None
    total = sum((value * weight for value, weight in usable), Decimal("0"))
    return (total / total_weight).quantize(Decimal("0.1"))


def quality_from_measures(items: Iterable[HarvestMeasure]) -> dict:
    records = list(items)
    moisture_pairs: list[tuple[Decimal, Decimal]] = []
    damaged_pairs: list[tuple[Decimal, Decimal]] = []
    empty_pairs: list[tuple[Decimal, Decimal]] = []
    foreign_pairs: list[tuple[Decimal, Decimal]] = []
    categories: dict[HarvestQualityCategory, dict[str, Decimal | int]] = defaultdict(
        lambda: {"net_kg": Decimal("0"), "event_count": 0}
    )
    for item in records:
        weight = quantity_kg(item.net, item.unit)
        if weight is None or weight <= 0:
            continue
        if item.moisture_percent is not None:
            moisture_pairs.append((item.moisture_percent, weight))
        if item.damaged_percent is not None:
            damaged_pairs.append((item.damaged_percent, weight))
        if item.empty_nuts_percent is not None:
            empty_pairs.append((item.empty_nuts_percent, weight))
        if item.foreign_material_percent is not None:
            foreign_pairs.append((item.foreign_material_percent, weight))
        if item.quality_category is not None:
            bucket = categories[item.quality_category]
            bucket["net_kg"] = Decimal(str(bucket["net_kg"])) + weight
            bucket["event_count"] = int(bucket["event_count"]) + 1

    def average(pairs: list[tuple[Decimal, Decimal]]) -> dict:
        value = weighted_average(pairs)
        return {
            "available": value is not None,
            "value": value,
            "method": "weighted" if value is not None else None,
            "sample_count": len(pairs),
        }

    category_rows = [
        {
            "category": category,
            "net_kg": Decimal(str(payload["net_kg"])),
            "event_count": int(payload["event_count"]),
        }
        for category, payload in sorted(categories.items(), key=lambda item: item[0].value)
    ]
    recorded = any(
        (
            moisture_pairs,
            damaged_pairs,
            empty_pairs,
            foreign_pairs,
            category_rows,
        )
    )
    return {
        "recorded": recorded,
        "moisture": average(moisture_pairs),
        "damaged": average(damaged_pairs),
        "empty_nuts": average(empty_pairs),
        "foreign_material": average(foreign_pairs),
        "categories": category_rows,
    }


def yield_per_hectare(net_kg: Decimal | None, area_hectares: Decimal | None) -> Decimal | None:
    return ratio(net_kg, area_hectares)


def yield_per_tree(net_kg: Decimal | None, tree_count: int | Decimal | None) -> Decimal | None:
    return ratio(net_kg, tree_count)


def comparison_percent(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    return percent_change(current, previous)


def available_production_years(
    harvest_years: Iterable[int],
    *,
    selected_year: int,
    current_year: int,
    planting_year: int | None = None,
) -> list[int]:
    years = {current_year, selected_year, current_year - 1, current_year + 1}
    years.update(int(year) for year in harvest_years)
    if planting_year:
        years.add(planting_year)
    return sorted(year for year in years if 1990 <= year <= 2100)


__all__ = [
    "HarvestMeasure",
    "MISSING_PREVIOUS_YEAR",
    "PARCEL_TOTAL_NOTE",
    "available_production_years",
    "comparison_percent",
    "first_last_dates",
    "net_quantity",
    "parcel_scope_only",
    "quality_from_measures",
    "quantity_kg",
    "timeline_points",
    "total_kg",
    "validate_quantities",
    "weighted_average",
    "year_bounds",
    "yield_per_hectare",
    "yield_per_tree",
]
