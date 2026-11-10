from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.varieties import DEFAULT_VARIETIES
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _parcel_payload(name: str, rows: int = 4, trees: int = 5) -> dict[str, Any]:
    return {
        "name": name,
        "area_hectares": 0.6,
        "row_count": rows,
        "trees_per_row": trees,
        "row_spacing_m": 5,
        "tree_spacing_m": 3.5,
        "planting_year": 2022,
        "starting_tree_number": 1,
        "varieties": DEFAULT_VARIETIES,
        "row_plan": [
            {"row_number": index, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []}
            for index in range(1, rows + 1)
        ],
    }


class PlantingOrganicApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def _create_parcel(self, **kwargs: Any) -> dict[str, Any]:
        payload = _parcel_payload(f"AT-plant-{uuid4().hex[:8]}", **kwargs)
        created = self.client.post("/api/v1/parcels", headers=self.headers, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def test_existing_parcel_defaults_are_conventional(self) -> None:
        parcel = self._create_parcel()
        self.assertEqual(parcel.get("production_method", "conventional"), "conventional")
        self.assertEqual(parcel.get("organic_scope", "none"), "none")
        summary = self.client.get(
            f"/api/v1/parcels/{parcel['id']}/planting-summary",
            headers=self.headers,
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        body = summary.json()
        self.assertEqual(body["production_method"], "conventional")
        self.assertGreaterEqual(body["total_active_trees"], 1)

    def test_multi_year_batches_and_row_range(self) -> None:
        parcel = self._create_parcel(rows=6, trees=10)
        parcel_id = parcel["id"]
        first = self.client.post(
            f"/api/v1/parcels/{parcel_id}/planting-batches",
            headers=self.headers,
            json={
                "year": 2022,
                "quantity": 30,
                "scope_type": "row",
                "row_number_from": 1,
                "row_number_to": 3,
            },
        )
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            f"/api/v1/parcels/{parcel_id}/planting-batches",
            headers=self.headers,
            json={
                "year": 2023,
                "quantity": 30,
                "scope_type": "row",
                "row_number_from": 4,
                "row_number_to": 6,
            },
        )
        self.assertEqual(second.status_code, 201, second.text)
        summary = self.client.get(
            f"/api/v1/parcels/{parcel_id}/planting-summary",
            headers=self.headers,
        ).json()
        years = {item["year"]: item["tree_count"] for item in summary["years"]}
        self.assertIn(2022, years)
        self.assertIn(2023, years)
        self.assertEqual(len(summary["batches"]), 2)

    def test_quantity_limits_trees_on_same_parcel_scope(self) -> None:
        """Second period must not overwrite the whole parcel when quantity is partial."""
        parcel = self._create_parcel(rows=4, trees=5)
        parcel_id = parcel["id"]
        # Clear mixed seed years by applying an explicit first period for half.
        first = self.client.post(
            f"/api/v1/parcels/{parcel_id}/planting-batches",
            headers=self.headers,
            json={"year": 2020, "quantity": 10, "scope_type": "parcel", "row_number_from": 1, "row_number_to": 4},
        )
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            f"/api/v1/parcels/{parcel_id}/planting-batches",
            headers=self.headers,
            json={"year": 2021, "quantity": 10, "scope_type": "parcel", "row_number_from": 1, "row_number_to": 4},
        )
        self.assertEqual(second.status_code, 201, second.text)
        summary = self.client.get(
            f"/api/v1/parcels/{parcel_id}/planting-summary",
            headers=self.headers,
        ).json()
        years = {item["year"]: item["tree_count"] for item in summary["years"]}
        self.assertEqual(years.get(2020), 10)
        self.assertEqual(years.get(2021), 10)
        self.assertEqual(summary["planting_period_label"], "2020–2021")

    def test_set_planting_distribution_replaces_years(self) -> None:
        parcel = self._create_parcel(rows=4, trees=5)
        parcel_id = parcel["id"]
        response = self.client.put(
            f"/api/v1/parcels/{parcel_id}/planting-distribution",
            headers=self.headers,
            json={
                "years": [
                    {"year": 2022, "tree_count": 12},
                    {"year": 2024, "tree_count": 8},
                ]
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        years = {item["year"]: item["tree_count"] for item in body["years"]}
        self.assertEqual(years, {2022: 12, 2024: 8})
        self.assertEqual(body["planting_period_label"], "2022–2024")
        self.assertEqual(len(body["batches"]), 2)

        bad = self.client.put(
            f"/api/v1/parcels/{parcel_id}/planting-distribution",
            headers=self.headers,
            json={"years": [{"year": 2022, "tree_count": 5}]},
        )
        self.assertEqual(bad.status_code, 422, bad.text)

    def test_organic_entire_and_part(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        updated = self.client.patch(
            f"/api/v1/parcels/{parcel_id}",
            headers=self.headers,
            json={"production_method": "organic", "organic_scope": "entire_parcel"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["production_method"], "organic")
        self.assertEqual(updated.json()["organic_scope"], "entire_parcel")

        part = self.client.patch(
            f"/api/v1/parcels/{parcel_id}",
            headers=self.headers,
            json={"organic_scope": "part_of_parcel"},
        )
        self.assertEqual(part.status_code, 200, part.text)
        rows = self.client.get(f"/api/v1/parcels/{parcel_id}/rows", headers=self.headers).json()
        chosen = [rows[0]["id"]]
        organic_rows = self.client.put(
            f"/api/v1/parcels/{parcel_id}/organic-rows",
            headers=self.headers,
            json={"row_ids": chosen},
        )
        self.assertEqual(organic_rows.status_code, 200, organic_rows.text)
        flags = {item["id"]: item["is_organic"] for item in organic_rows.json()}
        self.assertTrue(flags[chosen[0]])
        for row_id, flag in flags.items():
            if row_id != chosen[0]:
                self.assertFalse(flag)

    def test_conventional_rejects_organic_scope(self) -> None:
        parcel = self._create_parcel()
        response = self.client.patch(
            f"/api/v1/parcels/{parcel['id']}",
            headers=self.headers,
            json={"production_method": "conventional", "organic_scope": "entire_parcel"},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_foreign_parcel_hidden(self) -> None:
        response = self.client.get(
            f"/api/v1/parcels/{uuid4()}/planting-summary",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)
