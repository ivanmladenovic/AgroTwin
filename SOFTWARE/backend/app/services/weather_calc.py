from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Belgrade"
FORECAST_DAYS = 7
YR_COORD_QUANTUM = Decimal("0.0001")

_DAY_SUFFIXES = ("_day", "_night", "_polartwilight")
_SYMBOL_SEVERITY = (
    "clearsky",
    "fair",
    "partlycloudy",
    "cloudy",
    "fog",
    "lightrainshowers",
    "lightrain",
    "rainshowers",
    "rain",
    "heavyrainshowers",
    "heavyrain",
    "lightsleetshowers",
    "lightsleet",
    "sleetshowers",
    "sleet",
    "heavysleetshowers",
    "heavysleet",
    "lightsnowshowers",
    "lightsnow",
    "snowshowers",
    "snow",
    "heavysnowshowers",
    "heavysnow",
)


@dataclass
class DailyForecast:
    date: date
    min_temperature: float | None = None
    max_temperature: float | None = None
    precipitation: float = 0.0
    precipitation_probability: int | None = None
    symbol_code: str | None = None


@dataclass
class _DayBucket:
    temperatures: list[float] = field(default_factory=list)
    period_min: list[float] = field(default_factory=list)
    period_max: list[float] = field(default_factory=list)
    precip_1h: list[tuple[datetime, float]] = field(default_factory=list)
    precip_6h: list[tuple[datetime, float]] = field(default_factory=list)
    probabilities: list[float] = field(default_factory=list)
    symbols: list[tuple[datetime, str]] = field(default_factory=list)


def yr_coordinate(value: Decimal | float | int | str) -> Decimal:
    """Round coordinates to 4 decimal places for Yr requests."""
    return Decimal(str(value)).quantize(YR_COORD_QUANTUM, rounding=ROUND_HALF_UP)


def parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def daily_forecast_to_dict(day: DailyForecast) -> dict[str, Any]:
    return {
        "date": day.date.isoformat(),
        "min_temperature": day.min_temperature,
        "max_temperature": day.max_temperature,
        "precipitation": day.precipitation,
        "precipitation_probability": day.precipitation_probability,
        "symbol_code": day.symbol_code,
    }


def normalize_compact_forecast(
    payload: dict[str, Any],
    timezone_name: str = DEFAULT_TIMEZONE,
    *,
    now: datetime | None = None,
    days: int = FORECAST_DAYS,
) -> list[DailyForecast]:
    tz = resolve_timezone(timezone_name)
    local_now = now.astimezone(tz) if now is not None else datetime.now(tz)
    start_date = local_now.date()
    wanted = {start_date + timedelta(days=offset) for offset in range(days)}
    buckets: dict[date, _DayBucket] = {day: _DayBucket() for day in wanted}

    timeseries = _timeseries(payload)
    for point in timeseries:
        time_raw = point.get("time")
        data = point.get("data")
        if not isinstance(time_raw, str) or not isinstance(data, dict):
            continue
        try:
            utc_time = parse_utc(time_raw)
        except ValueError:
            continue
        local_time = utc_time.astimezone(tz)
        bucket = buckets.get(local_time.date())
        if bucket is None:
            continue
        _collect_point(bucket, data, local_time, utc_time)

    result: list[DailyForecast] = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        built = _build_day(day, buckets[day])
        if built is None:
            continue
        result.append(built)
    return result


def _timeseries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        return []
    series = properties.get("timeseries")
    if not isinstance(series, list):
        return []
    return [item for item in series if isinstance(item, dict)]


def _collect_point(bucket: _DayBucket, data: dict[str, Any], local_time: datetime, utc_time: datetime) -> None:
    instant = _details(data.get("instant"))
    temperature = _number(instant.get("air_temperature"))
    if temperature is not None:
        bucket.temperatures.append(temperature)

    next_1 = data.get("next_1_hours")
    next_6 = data.get("next_6_hours")
    next_12 = data.get("next_12_hours")

    details_1 = _details(next_1)
    details_6 = _details(next_6)
    details_12 = _details(next_12)

    amount_1 = _number(details_1.get("precipitation_amount"))
    if amount_1 is not None:
        bucket.precip_1h.append((local_time, amount_1))

    amount_6 = _number(details_6.get("precipitation_amount"))
    if amount_6 is not None:
        bucket.precip_6h.append((utc_time, amount_6))

    period_min = _number(details_6.get("air_temperature_min"))
    period_max = _number(details_6.get("air_temperature_max"))
    if period_min is not None:
        bucket.period_min.append(period_min)
    if period_max is not None:
        bucket.period_max.append(period_max)

    for details in (details_1, details_6, details_12):
        probability = _number(details.get("probability_of_precipitation"))
        if probability is not None:
            bucket.probabilities.append(probability)

    symbol = _symbol(next_6) or _symbol(next_1) or _symbol(next_12)
    if symbol:
        bucket.symbols.append((local_time, symbol))


def _build_day(day: date, bucket: _DayBucket) -> DailyForecast | None:
    temps = bucket.temperatures + bucket.period_min + bucket.period_max
    if not temps and not bucket.precip_1h and not bucket.precip_6h and not bucket.symbols:
        return None

    min_temperature = min(bucket.temperatures + bucket.period_min) if (bucket.temperatures or bucket.period_min) else None
    max_temperature = max(bucket.temperatures + bucket.period_max) if (bucket.temperatures or bucket.period_max) else None
    if min_temperature is None and temps:
        min_temperature = min(temps)
    if max_temperature is None and temps:
        max_temperature = max(temps)

    precipitation = _daily_precipitation(bucket)
    probability = None
    if bucket.probabilities:
        probability = int(round(max(bucket.probabilities)))
        probability = max(0, min(100, probability))

    return DailyForecast(
        date=day,
        min_temperature=_round1(min_temperature) if min_temperature is not None else None,
        max_temperature=_round1(max_temperature) if max_temperature is not None else None,
        precipitation=_round1(precipitation),
        precipitation_probability=probability,
        symbol_code=_representative_symbol(day, bucket),
    )


def _daily_precipitation(bucket: _DayBucket) -> float:
    if bucket.precip_1h:
        return sum(amount for _, amount in bucket.precip_1h)
    return sum(_non_overlapping_6h(bucket.precip_6h))


def _non_overlapping_6h(values: list[tuple[datetime, float]]) -> list[float]:
    chosen: list[float] = []
    last_start: datetime | None = None
    for start, amount in sorted(values, key=lambda item: item[0]):
        if start.hour % 6 != 0:
            continue
        if last_start is not None and start < last_start + timedelta(hours=6):
            continue
        chosen.append(amount)
        last_start = start
    if chosen:
        return chosen
    last_start = None
    fallback: list[float] = []
    for start, amount in sorted(values, key=lambda item: item[0]):
        if last_start is not None and start < last_start + timedelta(hours=6):
            continue
        fallback.append(amount)
        last_start = start
    return fallback


def _representative_symbol(day: date, bucket: _DayBucket) -> str | None:
    if not bucket.symbols:
        return None
    tzinfo = bucket.symbols[0][0].tzinfo
    noon = datetime.combine(day, time(12, 0), tzinfo=tzinfo)
    closest = min(bucket.symbols, key=lambda item: abs((item[0] - noon).total_seconds()))
    wet = sum(amount for _, amount in bucket.precip_1h) if bucket.precip_1h else sum(_non_overlapping_6h(bucket.precip_6h))
    if wet > 0.1:
        daytime = [item for item in bucket.symbols if 6 <= item[0].hour < 18]
        pool = daytime or bucket.symbols
        return max(pool, key=lambda item: (_symbol_rank(item[1]), -abs((item[0] - noon).total_seconds())))[1]
    return closest[1]


def _symbol_rank(code: str) -> int:
    base = _base_symbol(code)
    score = 0
    for index, name in enumerate(_SYMBOL_SEVERITY):
        if base == name:
            score = index
            break
    if "thunder" in base:
        score += 40
    return score


def _base_symbol(code: str) -> str:
    for suffix in _DAY_SUFFIXES:
        if code.endswith(suffix):
            return code[: -len(suffix)]
    return code


def _symbol(period: Any) -> str | None:
    if not isinstance(period, dict):
        return None
    summary = period.get("summary")
    if not isinstance(summary, dict):
        return None
    code = summary.get("symbol_code")
    return str(code) if code else None


def _details(period: Any) -> dict[str, Any]:
    if not isinstance(period, dict):
        return {}
    details = period.get("details")
    return details if isinstance(details, dict) else {}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round1(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
