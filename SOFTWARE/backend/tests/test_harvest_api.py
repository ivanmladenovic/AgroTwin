from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from time import perf_counter
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


def _money(value: str | int | float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


def _parcel_payload(name: str, rows: int = 2, trees: int = 3) -> dict[str, Any]:
    return {
        "name": name,
        "area_hectares": 0.5,
        "row_count": rows,
        "trees_per_row": trees,
        "row_spacing_m": 5,
        "tree_spacing_m": 3.5,
        "planting_year": 2024,
        "starting_tree_number": 1,
        "varieties": DEFAULT_VARIETIES,
        "row_plan": [
            {"row_number": index, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []}
            for index in range(1, rows + 1)
        ],
    }


class HarvestApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        cls.assertGreaterEqual = super().assertGreaterEqual
        if parcels.status_code != 200:
            raise AssertionError(parcels.text)
        payload = parcels.json()
        if not payload:
            raise AssertionError("Nema parcela")
        cls.kusiljevo = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        cls.kusiljevo_id = cls.kusiljevo["id"]

    def _create_parcel(self) -> dict[str, Any]:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json=_parcel_payload(f"AT-harvest-{uuid4().hex[:8]}"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def _rows(self, parcel_id: str) -> list[dict[str, Any]]:
        response = self.client.get(f"/api/v1/parcels/{parcel_id}/rows", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _trees(self, parcel_id: str, row_id: str) -> list[dict[str, Any]]:
        response = self.client.get(f"/api/v1/parcels/{parcel_id}/trees", params={"row_id": row_id}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _create_harvest(self, parcel_id: str, payload: dict[str, Any], expected: int = 201) -> Any:
        response = self.client.post(f"/api/v1/parcels/{parcel_id}/harvests", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if expected != 204 else None

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{self.kusiljevo_id}/production?year=2026")
        self.assertEqual(response.status_code, 401)

    def test_foreign_parcel_is_hidden(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{uuid4()}/production?year=2026", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_create_parcel_row_and_tree_harvests_and_net(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        try:
            rows = self._rows(parcel_id)
            trees = self._trees(parcel_id, rows[0]["id"])
            parcel_harvest = self._create_harvest(
                parcel_id,
                {
                    "harvested_on": "2026-09-10",
                    "scope_type": "parcel",
                    "gross_quantity": "1500",
                    "loss_quantity": "80",
                    "unit": "kg",
                    "moisture_percent": "8.5",
                    "quality_category": "standard",
                    "notes": "Test parcela",
                },
            )
            self.assertEqual(_money(parcel_harvest["net_quantity"]), Decimal("1420"))
            row_harvest = self._create_harvest(
                parcel_id,
                {
                    "harvested_on": "2026-09-11",
                    "scope_type": "row",
                    "row_id": rows[0]["id"],
                    "gross_quantity": "84",
                    "loss_quantity": "4",
                },
            )
            self.assertEqual(row_harvest["scope_type"], "row")
            self.assertEqual(row_harvest["row_id"], rows[0]["id"])
            tree_harvest = self._create_harvest(
                parcel_id,
                {
                    "harvested_on": "2026-09-12",
                    "scope_type": "tree",
                    "tree_id": trees[0]["id"],
                    "gross_quantity": "4.2",
                    "loss_quantity": "0",
                },
            )
            self.assertEqual(tree_harvest["scope_type"], "tree")
            self.assertEqual(tree_harvest["tree_id"], trees[0]["id"])
            self.assertEqual(tree_harvest["row_id"], rows[0]["id"])

            production = self.client.get(
                f"/api/v1/parcels/{parcel_id}/production",
                params={"year": 2026},
                headers=self.headers,
            )
            self.assertEqual(production.status_code, 200, production.text)
            body = production.json()
            self.assertTrue(body["parcel_total_recorded"])
            self.assertEqual(_money(body["total_net_yield"]["value"]), Decimal("1420"))
            self.assertEqual(body["harvest_event_count"], 1)
            self.assertEqual(body["all_event_count"], 3)
            self.assertEqual(len(body["row_summary"]), 1)
            self.assertEqual(len(body["tree_summary"]), 1)
            self.assertEqual(_money(body["row_summary"][0]["net_kg"]), Decimal("80"))
            self.assertEqual(_money(body["tree_summary"][0]["net_kg"]), Decimal("4.2"))
            self.assertEqual(body["first_harvest_date"], "2026-09-10")
            self.assertEqual(body["last_harvest_date"], "2026-09-10")
            self.assertEqual(_money(body["yield_per_hectare"]["value"]), Decimal("2840.00"))
        finally:
            deleted = self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)
            self.assertEqual(deleted.status_code, 204, deleted.text)

    def test_invalid_loss_and_quality_and_scope(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        try:
            too_much_loss = self.client.post(
                f"/api/v1/parcels/{parcel_id}/harvests",
                headers=self.headers,
                json={"harvested_on": "2026-09-10", "scope_type": "parcel", "gross_quantity": "100", "loss_quantity": "120"},
            )
            self.assertEqual(too_much_loss.status_code, 422)
            bad_moisture = self.client.post(
                f"/api/v1/parcels/{parcel_id}/harvests",
                headers=self.headers,
                json={"harvested_on": "2026-09-10", "scope_type": "parcel", "gross_quantity": "100", "moisture_percent": "140"},
            )
            self.assertEqual(bad_moisture.status_code, 422)
            missing_row = self.client.post(
                f"/api/v1/parcels/{parcel_id}/harvests",
                headers=self.headers,
                json={"harvested_on": "2026-09-10", "scope_type": "row", "gross_quantity": "10"},
            )
            self.assertEqual(missing_row.status_code, 422)
            farm_scope = self.client.post(
                f"/api/v1/parcels/{parcel_id}/harvests",
                headers=self.headers,
                json={"harvested_on": "2026-09-10", "scope_type": "farm", "gross_quantity": "10"},
            )
            self.assertEqual(farm_scope.status_code, 422)
        finally:
            self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)

    def test_cross_parcel_row_and_tree_rejected(self) -> None:
        first = self._create_parcel()
        second = self._create_parcel()
        try:
            foreign_row = self._rows(second["id"])[0]
            foreign_tree = self._trees(second["id"], foreign_row["id"])[0]
            row_response = self.client.post(
                f"/api/v1/parcels/{first['id']}/harvests",
                headers=self.headers,
                json={
                    "harvested_on": "2026-09-10",
                    "scope_type": "row",
                    "row_id": foreign_row["id"],
                    "gross_quantity": "10",
                },
            )
            self.assertEqual(row_response.status_code, 422, row_response.text)
            tree_response = self.client.post(
                f"/api/v1/parcels/{first['id']}/harvests",
                headers=self.headers,
                json={
                    "harvested_on": "2026-09-10",
                    "scope_type": "tree",
                    "tree_id": foreign_tree["id"],
                    "gross_quantity": "2",
                },
            )
            self.assertEqual(tree_response.status_code, 422, tree_response.text)
        finally:
            self.client.delete(f"/api/v1/parcels/{first['id']}", headers=self.headers)
            self.client.delete(f"/api/v1/parcels/{second['id']}", headers=self.headers)

    def test_year_filter_and_empty_year(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        try:
            self._create_harvest(
                parcel_id,
                {"harvested_on": "2026-09-10", "scope_type": "parcel", "gross_quantity": "100", "loss_quantity": "0"},
            )
            self._create_harvest(
                parcel_id,
                {"harvested_on": "2025-09-10", "scope_type": "parcel", "gross_quantity": "40", "loss_quantity": "0"},
            )
            year_2026 = self.client.get(f"/api/v1/parcels/{parcel_id}/harvests", params={"year": 2026}, headers=self.headers)
            year_2025 = self.client.get(f"/api/v1/parcels/{parcel_id}/harvests", params={"year": 2025}, headers=self.headers)
            empty = self.client.get(f"/api/v1/parcels/{parcel_id}/production", params={"year": 2024}, headers=self.headers)
            self.assertEqual(len(year_2026.json()), 1)
            self.assertEqual(len(year_2025.json()), 1)
            body = empty.json()
            self.assertFalse(body["recorded"])
            self.assertFalse(body["total_net_yield"]["available"])
            self.assertIsNone(body["total_net_yield"]["value"])
            self.assertEqual(body["all_event_count"], 0)
            self.assertFalse(body["comparison"]["available"])
            self.assertIn("prethodnu godinu", body["comparison"]["message"])
        finally:
            self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)

    def test_previous_year_comparison_and_edit_delete(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        try:
            first = self._create_harvest(
                parcel_id,
                {"harvested_on": "2025-09-01", "scope_type": "parcel", "gross_quantity": "1000", "loss_quantity": "0"},
            )
            created = self._create_harvest(
                parcel_id,
                {
                    "harvested_on": "2026-09-01",
                    "scope_type": "parcel",
                    "gross_quantity": "400",
                    "loss_quantity": "0",
                    "moisture_percent": "8.0",
                },
            )
            updated = self.client.patch(
                f"/api/v1/parcels/{parcel_id}/harvests/{created['id']}",
                headers=self.headers,
                json={"gross_quantity": "1200", "loss_quantity": "80"},
            )
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(_money(updated.json()["net_quantity"]), Decimal("1120"))
            production = self.client.get(
                f"/api/v1/parcels/{parcel_id}/production",
                params={"year": 2026},
                headers=self.headers,
            ).json()
            self.assertEqual(_money(production["total_net_yield"]["value"]), Decimal("1120"))
            self.assertTrue(production["comparison"]["available"])
            self.assertEqual(_money(production["comparison"]["previous_net_yield"]["value"]), Decimal("1000"))
            self.assertEqual(_money(production["comparison"]["net_yield_change"]["percent"]), Decimal("12.0"))
            deleted = self.client.delete(
                f"/api/v1/parcels/{parcel_id}/harvests/{created['id']}",
                headers=self.headers,
            )
            self.assertEqual(deleted.status_code, 204, deleted.text)
            after = self.client.get(
                f"/api/v1/parcels/{parcel_id}/production",
                params={"year": 2026},
                headers=self.headers,
            ).json()
            self.assertFalse(after["recorded"])
            still_previous = self.client.get(
                f"/api/v1/parcels/{parcel_id}/harvests/{first['id']}",
                headers=self.headers,
            )
            self.assertEqual(still_previous.status_code, 200)
        finally:
            self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)

    def test_kusiljevo_2026_seed_and_performance(self) -> None:
        started = perf_counter()
        response = self.client.get(
            f"/api/v1/parcels/{self.kusiljevo_id}/production",
            params={"year": 2026},
            headers=self.headers,
        )
        elapsed = perf_counter() - started
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertLess(elapsed, 2.0)
        if not body["parcel_total_recorded"]:
            self.skipTest("Kusiljevo harvest seed nije primenjen")
        self.assertEqual(_money(body["total_net_yield"]["value"]), Decimal("1420"))
        self.assertEqual(body["harvest_event_count"], 3)
        self.assertGreaterEqual(body["all_event_count"], 3)
        self.assertEqual(body["first_harvest_date"], "2026-09-10")
        self.assertEqual(body["last_harvest_date"], "2026-09-20")
        self.assertTrue(body["yield_per_hectare"]["available"])
        self.assertEqual(len(body["timeline"]), 3)
        self.assertEqual(_money(body["timeline"][-1]["cumulative_net_kg"]), Decimal("1420"))
        csv_response = self.client.get(
            f"/api/v1/parcels/{self.kusiljevo_id}/harvests/export.csv",
            params={"year": 2026},
            headers=self.headers,
        )
        self.assertEqual(csv_response.status_code, 200, csv_response.text)
        self.assertIn("gross_quantity", csv_response.text)
        self.assertNotIn("price", csv_response.text)
        self.assertNotIn("revenue", csv_response.text)
        report = self.client.get(
            f"/api/v1/parcels/{self.kusiljevo_id}/report",
            params={"year": 2026},
            headers=self.headers,
        ).json()
        self.assertEqual(_money(report["yield_summary"]["total_kg"]), Decimal("1420"))
        self.assertEqual(report["yield_summary"]["harvest_events"], 3)
        self.assertEqual(report["yield_summary"]["source"], "harvest_event")
