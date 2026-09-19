from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
import sys
from zoneinfo import ZoneInfo

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.varieties import DEFAULT_VARIETIES
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app
from app.services.weather_calc import DEFAULT_TIMEZONE
from app.services.weather_provider import YrFetchResult, YrWeatherError, YrWeatherProvider


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _parcel_payload(name: str, maps_url: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "area_hectares": 0.5,
        "row_count": 1,
        "trees_per_row": 2,
        "row_spacing_m": 5,
        "tree_spacing_m": 3.5,
        "planting_year": 2024,
        "starting_tree_number": 1,
        "varieties": DEFAULT_VARIETIES,
        "row_plan": [{"row_number": 1, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []}],
    }
    if maps_url:
        payload["maps_url"] = maps_url
    return payload


def _yr_payload(now: datetime | None = None) -> dict[str, Any]:
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    start = (now or datetime.now(tz)).astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    series = []
    for day in range(8):
        for hour in (0, 6, 12, 18):
            local = start + timedelta(days=day, hours=hour)
            series.append(
                {
                    "time": local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "data": {
                        "instant": {"details": {"air_temperature": 14 + day + hour / 10}},
                        "next_6_hours": {
                            "summary": {"symbol_code": "partlycloudy_day" if hour < 18 else "partlycloudy_night"},
                            "details": {
                                "precipitation_amount": 0.3 if hour == 12 else 0.0,
                                "air_temperature_min": 12 + day,
                                "air_temperature_max": 24 + day,
                                "probability_of_precipitation": 20 if hour == 12 else 5,
                            },
                        },
                    },
                }
            )
    return {"properties": {"meta": {"updated_at": "2026-09-15T06:00:00Z"}, "timeseries": series}}


def _success_result() -> YrFetchResult:
    return YrFetchResult(
        payload=_yr_payload(),
        not_modified=False,
        last_modified="Tue, 15 Sep 2026 06:00:00 GMT",
        expires_at=None,
        source_updated_at=datetime(2026, 9, 15, 6, 0, tzinfo=timezone.utc),
    )


class WeatherApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        if parcels.status_code != 200:
            raise AssertionError(parcels.text)
        payload = parcels.json()
        if not payload:
            raise AssertionError("Nema parcela")
        cls.kusiljevo = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        cls.kusiljevo_id = cls.kusiljevo["id"]

    def _create_parcel(self, maps_url: str | None = "https://www.google.com/maps/@44.2574,21.102738,17z") -> dict[str, Any]:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json=_parcel_payload(f"AT-weather-{uuid4().hex[:8]}", maps_url=maps_url),
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def _delete(self, parcel_id: str) -> None:
        self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{self.kusiljevo_id}/weather")
        self.assertEqual(response.status_code, 401)

    def test_foreign_parcel_is_hidden(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{uuid4()}/weather", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_missing_location_does_not_call_yr(self) -> None:
        parcel = self._create_parcel(maps_url=None)
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(YrWeatherProvider, "fetch", fake_fetch):
                response = self.client.get(f"/api/v1/parcels/{parcel['id']}/weather", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertFalse(body["available"])
            self.assertEqual(body["status"], "no_location")
            self.assertEqual(calls["n"], 0)
            self.assertEqual(body["forecast"], [])
        finally:
            self._delete(parcel["id"])

    def test_valid_forecast_is_normalized_and_cached(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(YrWeatherProvider, "fetch", fake_fetch):
                first = self.client.get(f"/api/v1/parcels/{parcel['id']}/weather", headers=self.headers)
                second = self.client.get(f"/api/v1/parcels/{parcel['id']}/weather", headers=self.headers)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(second.status_code, 200, second.text)
            body = first.json()
            self.assertTrue(body["available"])
            self.assertEqual(body["status"], "ok")
            self.assertEqual(body["source"], "Yr")
            self.assertEqual(len(body["forecast"]), 7)
            self.assertEqual(body["latitude"], 44.2574)
            self.assertEqual(body["longitude"], 21.1027)
            self.assertEqual(calls["n"], 1)
            self.assertEqual(second.json()["forecast"], body["forecast"])
            today = datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).date().isoformat()
            self.assertEqual(body["forecast"][0]["date"], today)
            self.assertIsNotNone(body["forecast"][0]["min_temperature"])
            self.assertIsNotNone(body["forecast"][0]["max_temperature"])
        finally:
            self._delete(parcel["id"])

    def test_failed_refresh_returns_cached_forecast(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _success_result()
            raise YrWeatherError(500, "provider_error")

        try:
            with patch.object(YrWeatherProvider, "fetch", fake_fetch):
                first = self.client.get(f"/api/v1/parcels/{parcel['id']}/weather", headers=self.headers)
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(first.json()["status"], "ok")
                with patch("app.services.weather.WeatherService._cache_is_fresh", return_value=False):
                    second = self.client.get(f"/api/v1/parcels/{parcel['id']}/weather", headers=self.headers)
            self.assertEqual(second.status_code, 200, second.text)
            body = second.json()
            self.assertTrue(body["available"])
            self.assertEqual(body["status"], "stale")
            self.assertEqual(len(body["forecast"]), 7)
            self.assertEqual(calls["n"], 2)
        finally:
            self._delete(parcel["id"])

    def test_concurrent_requests_refresh_once(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(YrWeatherProvider, "fetch", fake_fetch):
                with ThreadPoolExecutor(max_workers=3) as pool:
                    results = list(
                        pool.map(
                            lambda _: self.client.get(f"/api/v1/parcels/{parcel['id']}/weather", headers=self.headers),
                            range(3),
                        )
                    )
            self.assertTrue(all(item.status_code == 200 for item in results), [item.text for item in results])
            self.assertEqual(calls["n"], 1)
            self.assertEqual(len(results[0].json()["forecast"]), 7)
        finally:
            self._delete(parcel["id"])
