"""Aggregate normalized AgroTwin weather days. No agronomic interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


HOT_DAY_C = 30.0
FROST_DAY_C = 0.0
RAIN_MM = 0.1


@dataclass(frozen=True)
class WeatherDay:
    date: date
    min_temperature: float | None
    max_temperature: float | None
    precipitation: float | None
    precipitation_probability: int | None = None
    symbol_code: str | None = None


@dataclass(frozen=True)
class WeatherAggregates:
    period_start: date | None
    period_end: date | None
    minimum_temperature: float | None
    maximum_temperature: float | None
    average_temperature: float | None
    precipitation: float | None
    rainy_days: int
    hot_days: int
    frost_days: int
    record_count: int


def parse_weather_days(rows: list[dict[str, Any]] | None) -> list[WeatherDay]:
    days: list[WeatherDay] = []
    if not rows:
        return days
    for item in rows:
        if not isinstance(item, dict) or not item.get("date"):
            continue
        try:
            day = date.fromisoformat(str(item["date"]))
        except ValueError:
            continue
        days.append(
            WeatherDay(
                date=day,
                min_temperature=_float(item.get("min_temperature")),
                max_temperature=_float(item.get("max_temperature")),
                precipitation=_float(item.get("precipitation")),
                precipitation_probability=_int(item.get("precipitation_probability")),
                symbol_code=item.get("symbol_code") if isinstance(item.get("symbol_code"), str) else None,
            )
        )
    days.sort(key=lambda row: row.date)
    return days


def aggregate_weather(days: list[WeatherDay]) -> WeatherAggregates:
    if not days:
        return WeatherAggregates(None, None, None, None, None, None, 0, 0, 0, 0)
    mins = [row.min_temperature for row in days if row.min_temperature is not None]
    maxs = [row.max_temperature for row in days if row.max_temperature is not None]
    means: list[float] = []
    for row in days:
        if row.min_temperature is not None and row.max_temperature is not None:
            means.append((row.min_temperature + row.max_temperature) / 2)
        elif row.max_temperature is not None:
            means.append(row.max_temperature)
        elif row.min_temperature is not None:
            means.append(row.min_temperature)
    precip_values = [row.precipitation for row in days if row.precipitation is not None]
    rainy = sum(1 for row in days if row.precipitation is not None and row.precipitation > RAIN_MM)
    hot = sum(1 for row in days if row.max_temperature is not None and row.max_temperature >= HOT_DAY_C)
    frost = sum(1 for row in days if row.min_temperature is not None and row.min_temperature < FROST_DAY_C)
    return WeatherAggregates(
        period_start=days[0].date,
        period_end=days[-1].date,
        minimum_temperature=_round1(min(mins)) if mins else None,
        maximum_temperature=_round1(max(maxs)) if maxs else None,
        average_temperature=_round1(sum(means) / len(means)) if means else None,
        precipitation=_round1(sum(precip_values)) if precip_values else None,
        rainy_days=rainy,
        hot_days=hot,
        frost_days=frost,
        record_count=len(days),
    )


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _round1(value: float) -> float:
    return round(value, 1)
