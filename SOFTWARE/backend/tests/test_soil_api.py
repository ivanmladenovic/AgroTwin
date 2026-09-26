from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.varieties import DEFAULT_VARIETIES
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app
from app.soil.provider import SoilGridsError, SoilGridsFetchResult, SoilGridsProvider

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "soilgrids_query.json"


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


def _payload() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text())


def _success_result(payload: dict[str, Any] | None = None) -> SoilGridsFetchResult:
    return SoilGridsFetchResult(payload=payload or _payload(), dataset_version="2.0")


class SoilApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def _create_parcel(self, maps_url: str | None = "https://www.google.com/maps/@44.2574,21.102738,17z") -> dict[str, Any]:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json=_parcel_payload(f"AT-soil-{uuid4().hex[:8]}", maps_url=maps_url),
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def _delete(self, parcel_id: str) -> None:
        self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{uuid4()}/soil/profile")
        self.assertEqual(response.status_code, 401)

    def test_missing_coordinates_do_not_call_provider(self) -> None:
        parcel = self._create_parcel(maps_url=None)
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                response = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertFalse(body["available"])
            self.assertEqual(body["status"], "location_required")
            self.assertFalse(body["is_stale"])
            self.assertEqual(body["message"], "Lokacija parcele nije podešena.")
            self.assertEqual(body["source_type"], "modeled_estimate")
            self.assertEqual(body["source_label"], "Modelovana procena – SoilGrids")
            self.assertEqual(calls["n"], 0)
        finally:
            self._delete(parcel["id"])

    def test_profile_is_normalized_and_cached(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                first = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
                second = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(second.status_code, 200, second.text)
            body = first.json()
            self.assertTrue(body["available"])
            self.assertEqual(body["status"], "ok")
            self.assertFalse(body["is_stale"])
            self.assertEqual(body["provider"], "SoilGrids")
            self.assertEqual(body["source"], "SoilGrids")
            self.assertEqual(body["spatial_resolution"], "250 m")
            self.assertEqual(body["depths"][0], "0-5cm")
            self.assertTrue(body["is_modeled"])
            self.assertEqual(body["source_label"], "Modelovana procena – SoilGrids")
            by_key = {item["key"]: item for item in body["properties"]}
            self.assertEqual(by_key["ph"]["value"], 6.5)
            self.assertEqual(by_key["ph"]["source_label"], "Modelovana procena – SoilGrids")
            self.assertTrue(by_key["ph"]["is_modeled"])
            self.assertIsNone(by_key["ph"]["measured_at"])
            self.assertEqual(by_key["clay"]["value"], 37.0)
            self.assertEqual(by_key["clay"]["unit"], "%")
            self.assertEqual(by_key["organic_carbon"]["value"], 3.38)
            self.assertEqual(by_key["organic_carbon"]["unit"], "%")
            self.assertEqual(len(by_key["ph"]["depths"]), 6)
            self.assertEqual(calls["n"], 1)
            self.assertEqual(second.json()["properties"], body["properties"])
            self.assertFalse(body["can_refresh"])
        finally:
            self._delete(parcel["id"])

    def test_refresh_is_rate_limited(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                first = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
                refresh = self.client.post(f"/api/v1/parcels/{parcel['id']}/soil/refresh", headers=self.headers)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(refresh.status_code, 200, refresh.text)
            self.assertEqual(calls["n"], 1)
            self.assertTrue(refresh.json()["available"])
            self.assertIn("ograničeno", refresh.json()["message"])
        finally:
            self._delete(parcel["id"])

    def test_coordinate_change_invalidates_cache(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0, "coords": []}

        def fake_fetch(self, latitude, longitude):
            calls["n"] += 1
            calls["coords"].append((float(latitude), float(longitude)))
            return _success_result()

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                first = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
                self.assertEqual(first.status_code, 200, first.text)
                updated = self.client.patch(
                    f"/api/v1/parcels/{parcel['id']}",
                    headers=self.headers,
                    json={"maps_url": "https://www.google.com/maps/@44.4000,21.3000,17z"},
                )
                self.assertEqual(updated.status_code, 200, updated.text)
                second = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(second.status_code, 200, second.text)
            self.assertEqual(calls["n"], 2)
            self.assertNotEqual(calls["coords"][0], calls["coords"][1])
            self.assertEqual(second.json()["latitude"], 44.4)
            self.assertEqual(second.json()["longitude"], 21.3)
        finally:
            self._delete(parcel["id"])

    def test_partial_provider_response(self) -> None:
        parcel = self._create_parcel()
        payload = deepcopy(_payload())
        payload["properties"]["layers"] = [layer for layer in payload["properties"]["layers"] if layer["name"] != "soc"]

        def fake_fetch(self, *args, **kwargs):
            return _success_result(payload)

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                response = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertTrue(body["available"])
            self.assertEqual(body["status"], "partial")
            self.assertIn("organic_carbon", body["missing_properties"])
            by_key = {item["key"]: item for item in body["properties"]}
            self.assertTrue(by_key["ph"]["available"])
            self.assertFalse(by_key["organic_carbon"]["available"])
            self.assertIsNone(by_key["organic_carbon"]["value"])
        finally:
            self._delete(parcel["id"])

    def test_provider_failure_without_cache(self) -> None:
        parcel = self._create_parcel()

        def fake_fetch(self, *args, **kwargs):
            raise SoilGridsError(500, "unavailable")

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                response = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertFalse(body["available"])
            self.assertEqual(body["status"], "unavailable")
        finally:
            self._delete(parcel["id"])

    def test_provider_failure_returns_stale_cache(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _success_result()
            raise SoilGridsError(500, "unavailable")

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                first = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
                self.assertEqual(first.json()["status"], "ok")
                with patch("app.services.soil.SoilService._snapshot_is_fresh", return_value=False):
                    second = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(second.status_code, 200, second.text)
            body = second.json()
            self.assertTrue(body["available"])
            self.assertEqual(body["status"], "stale")
            self.assertTrue(body["is_stale"])
            self.assertIn("stariji", body["message"])
            self.assertEqual(calls["n"], 2)
        finally:
            self._delete(parcel["id"])

    def test_timeout_status(self) -> None:
        parcel = self._create_parcel()

        def fake_fetch(self, *args, **kwargs):
            raise SoilGridsError(0, "timeout")

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                response = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(response.json()["status"], "timeout")
            self.assertFalse(response.json()["available"])
        finally:
            self._delete(parcel["id"])

    def test_rate_limit_status(self) -> None:
        parcel = self._create_parcel()

        def fake_fetch(self, *args, **kwargs):
            raise SoilGridsError(429, "rate_limited")

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                response = self.client.get(f"/api/v1/parcels/{parcel['id']}/soil/profile", headers=self.headers)
            self.assertEqual(response.json()["status"], "rate_limited")
            self.assertFalse(response.json()["available"])
            self.assertIn("kasnije", response.json()["message"])
        finally:
            self._delete(parcel["id"])

    def test_concurrent_requests_refresh_once(self) -> None:
        parcel = self._create_parcel()
        calls = {"n": 0}

        def fake_fetch(self, *args, **kwargs):
            calls["n"] += 1
            return _success_result()

        try:
            with patch.object(SoilGridsProvider, "fetch", fake_fetch):
                with ThreadPoolExecutor(max_workers=3) as pool:
                    results = list(
                        pool.map(
                            lambda _: self.client.get(
                                f"/api/v1/parcels/{parcel['id']}/soil/profile",
                                headers=self.headers,
                            ),
                            range(3),
                        )
                    )
            self.assertTrue(all(item.status_code == 200 for item in results), [item.text for item in results])
            self.assertEqual(calls["n"], 1)
        finally:
            self._delete(parcel["id"])
