from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase
from zoneinfo import ZoneInfo

from app.core.maps import parse_google_maps_url
from app.services.weather_calc import (
    DEFAULT_TIMEZONE,
    normalize_compact_forecast,
    yr_coordinate,
)


def _point(time: datetime, **kwargs) -> dict:
    data: dict = {"instant": {"details": {}}}
    if "temperature" in kwargs:
        data["instant"]["details"]["air_temperature"] = kwargs["temperature"]
    if "precip_1h" in kwargs or "symbol_1h" in kwargs or "prob_1h" in kwargs:
        next_1: dict = {"summary": {}, "details": {}}
        if kwargs.get("symbol_1h"):
            next_1["summary"]["symbol_code"] = kwargs["symbol_1h"]
        if "precip_1h" in kwargs:
            next_1["details"]["precipitation_amount"] = kwargs["precip_1h"]
        if "prob_1h" in kwargs:
            next_1["details"]["probability_of_precipitation"] = kwargs["prob_1h"]
        data["next_1_hours"] = next_1
    if any(key in kwargs for key in ("precip_6h", "symbol_6h", "prob_6h", "tmin_6h", "tmax_6h")):
        next_6: dict = {"summary": {}, "details": {}}
        if kwargs.get("symbol_6h"):
            next_6["summary"]["symbol_code"] = kwargs["symbol_6h"]
        if "precip_6h" in kwargs:
            next_6["details"]["precipitation_amount"] = kwargs["precip_6h"]
        if "prob_6h" in kwargs:
            next_6["details"]["probability_of_precipitation"] = kwargs["prob_6h"]
        if "tmin_6h" in kwargs:
            next_6["details"]["air_temperature_min"] = kwargs["tmin_6h"]
        if "tmax_6h" in kwargs:
            next_6["details"]["air_temperature_max"] = kwargs["tmax_6h"]
        data["next_6_hours"] = next_6
    return {"time": time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "data": data}


def _payload(points: list[dict]) -> dict:
    return {"properties": {"meta": {"updated_at": "2026-09-15T06:00:00Z"}, "timeseries": points}}


class CoordinateTests(TestCase):
    def test_rounds_to_four_decimals(self) -> None:
        self.assertEqual(yr_coordinate(Decimal("44.123456")), Decimal("44.1235"))
        self.assertEqual(yr_coordinate("21.987654"), Decimal("21.9877"))


class LocationParseTests(TestCase):
    def test_valid_maps_url_extracts_coordinates(self) -> None:
        parsed = parse_google_maps_url("https://www.google.com/maps/@44.2574,21.102738,17z")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed.lat, 44.2574)
        self.assertAlmostEqual(parsed.lng, 21.102738)

    def test_invalid_maps_url_returns_none(self) -> None:
        self.assertIsNone(parse_google_maps_url("https://example.com/not-a-map"))
        self.assertIsNone(parse_google_maps_url("not a url"))

    def test_missing_location_is_empty(self) -> None:
        self.assertIsNone(parse_google_maps_url(""))
        self.assertIsNone(parse_google_maps_url("   "))


class ForecastNormalizationTests(TestCase):
    def setUp(self) -> None:
        self.tz = ZoneInfo(DEFAULT_TIMEZONE)
        self.now = datetime(2026, 9, 15, 8, 0, tzinfo=self.tz)

    def test_seven_local_days_and_timezone_boundary(self) -> None:
        points = []
        start = datetime(2026, 9, 15, 0, 0, tzinfo=self.tz)
        for day in range(7):
            for hour in range(24):
                local = start + timedelta(days=day, hours=hour)
                points.append(
                    _point(
                        local,
                        temperature=10 + day + (hour / 24),
                        precip_1h=0.1 if hour < 3 else 0,
                        symbol_1h="partlycloudy_day" if 6 <= hour < 18 else "partlycloudy_night",
                    )
                )
        # UTC 21:00 on Sep 14 is still Sep 14 in UTC, but 23:00 in Belgrade.
        # UTC 22:00 on Sep 14 is 00:00 Sep 15 in Belgrade and must count for the 15th.
        points.insert(
            0,
            _point(datetime(2026, 9, 14, 22, 0, tzinfo=timezone.utc), temperature=4.0, precip_1h=1.5, symbol_1h="rain"),
        )
        days = normalize_compact_forecast(_payload(points), DEFAULT_TIMEZONE, now=self.now)
        self.assertEqual(len(days), 7)
        self.assertEqual([item.date.isoformat() for item in days], [
            "2026-09-15",
            "2026-09-16",
            "2026-09-17",
            "2026-09-18",
            "2026-09-19",
            "2026-09-20",
            "2026-09-21",
        ])
        self.assertEqual(days[0].min_temperature, 4.0)
        self.assertGreaterEqual(days[0].precipitation, 1.5)

    def test_temperature_uses_min_and_max_not_first_hour(self) -> None:
        start = datetime(2026, 9, 15, 0, 0, tzinfo=self.tz)
        points = [
            _point(start.replace(hour=0), temperature=18.0, symbol_1h="clearsky_night"),
            _point(start.replace(hour=6), temperature=12.0, tmin_6h=11.0, tmax_6h=21.0, symbol_6h="fair_day"),
            _point(start.replace(hour=15), temperature=25.0, symbol_1h="clearsky_day"),
        ]
        days = normalize_compact_forecast(_payload(points), DEFAULT_TIMEZONE, now=self.now)
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0].min_temperature, 11.0)
        self.assertEqual(days[0].max_temperature, 25.0)

    def test_precipitation_sums_hourly_values(self) -> None:
        start = datetime(2026, 9, 15, 0, 0, tzinfo=self.tz)
        points = [
            _point(start.replace(hour=hour), temperature=16.0, precip_1h=0.4, symbol_1h="lightrain")
            for hour in range(6)
        ]
        days = normalize_compact_forecast(_payload(points), DEFAULT_TIMEZONE, now=self.now)
        self.assertEqual(days[0].precipitation, 2.4)

    def test_six_hour_precipitation_is_not_double_counted(self) -> None:
        start_utc = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
        points = [
            _point(start_utc + timedelta(hours=offset), temperature=14.0, precip_6h=1.2, symbol_6h="rain")
            for offset in range(6)
        ]
        days = normalize_compact_forecast(_payload(points), "UTC", now=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc))
        self.assertEqual(days[0].precipitation, 1.2)

    def test_missing_optional_fields_do_not_crash(self) -> None:
        point = {
            "time": "2026-09-15T10:00:00Z",
            "data": {"instant": {"details": {}}},
        }
        days = normalize_compact_forecast(_payload([point]), "UTC", now=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc))
        self.assertEqual(days, [])

        usable = {
            "time": "2026-09-15T10:00:00Z",
            "data": {
                "instant": {"details": {"air_temperature": 19}},
                "next_1_hours": {"summary": {}, "details": {}},
            },
        }
        days = normalize_compact_forecast(
            _payload([usable]),
            "UTC",
            now=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0].min_temperature, 19.0)
        self.assertEqual(days[0].max_temperature, 19.0)
        self.assertEqual(days[0].precipitation, 0.0)
        self.assertIsNone(days[0].precipitation_probability)
        self.assertIsNone(days[0].symbol_code)

    def test_probability_uses_available_maximum(self) -> None:
        start = datetime(2026, 9, 15, 12, 0, tzinfo=self.tz)
        points = [
            _point(start, temperature=20.0, precip_1h=0.2, prob_1h=10, symbol_1h="lightrain"),
            _point(start.replace(hour=15), temperature=18.0, precip_6h=1.0, prob_6h=40, symbol_6h="rain"),
        ]
        days = normalize_compact_forecast(_payload(points), DEFAULT_TIMEZONE, now=self.now)
        self.assertEqual(days[0].precipitation_probability, 40)
