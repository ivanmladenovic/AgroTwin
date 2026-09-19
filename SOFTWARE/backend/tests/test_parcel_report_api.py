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


class ParcelReportApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        if parcels.status_code != 200:
            raise AssertionError(parcels.text)
        payload = parcels.json()
        if not payload:
            raise AssertionError("Nema parcela za izveštaj")
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        cls.parcel_id = cls.parcel["id"]

    def _report(self, year: int, parcel_id: str | None = None) -> dict[str, Any]:
        target = parcel_id or self.parcel_id
        response = self.client.get(f"/api/v1/parcels/{target}/report", params={"year": year}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_foreign_parcel_is_hidden(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{uuid4()}/report?year=2026", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.get(f"/api/v1/parcels/{self.parcel_id}/report?year=2026")
        self.assertEqual(response.status_code, 401)

    def test_annual_and_historical_costs_match_cost_api(self) -> None:
        report = self._report(2026)
        financial = report["financial_summary"]
        self.assertTrue(financial["recorded"])
        summary = self.client.get(
            "/api/v1/costs/summary",
            params={"parcel_id": self.parcel_id},
            headers=self.headers,
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        costs = self.client.get(
            "/api/v1/costs",
            params={"parcel_id": self.parcel_id, "date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=self.headers,
        )
        self.assertEqual(costs.status_code, 200, costs.text)
        listed = [_money(item["amount"]) for item in costs.json()]
        self.assertEqual(_money(financial["annual_cost"]["value"]), sum(listed, Decimal("0")))
        historical = self.client.get(
            "/api/v1/costs",
            params={"parcel_id": self.parcel_id, "date_to": "2026-12-31"},
            headers=self.headers,
        )
        self.assertEqual(_money(financial["historical_cost"]["value"]), sum((_money(item["amount"]) for item in historical.json()), Decimal("0")))
        self.assertEqual(len(listed), len({item["id"] for item in costs.json()}))

    def test_category_and_activity_costs_do_not_double_count(self) -> None:
        report = self._report(2026)
        financial = report["financial_summary"]
        annual = _money(financial["annual_cost"]["value"])
        self.assertEqual(sum((_money(item["amount"]) for item in financial["by_category"]), Decimal("0")), annual)
        activity_total = sum((_money(item["amount"]) for item in financial["by_activity"]), Decimal("0"))
        self.assertLessEqual(activity_total, annual)
        self.assertLessEqual(len(financial["by_activity"]), 5)

    def test_tree_health_aggregation(self) -> None:
        report = self._report(2026)
        health = report["health_summary"]
        counted = health["healthy"] + health["monitoring"] + health["issue"] + health["unknown"]
        self.assertEqual(counted, health["total_trees"])
        self.assertEqual(health["attention_count"], health["issue"] + health["monitoring"])
        self.assertGreaterEqual(health["total_trees"], 1800)
        self.assertEqual(health["active_trees"] + health["removed"] + health["replaced"], health["total_trees"])

    def test_problem_aggregation_and_rows(self) -> None:
        report = self._report(2026)
        problems = report["problem_summary"]
        self.assertTrue(problems["recorded"])
        self.assertEqual(sum(item["count"] for item in problems["by_category"]), problems["total"])
        self.assertLessEqual(sum(item["count"] for item in problems["by_row"]), problems["total"])
        self.assertLessEqual(
            problems["open_count"] + problems["monitoring_count"] + problems["resolved_count"],
            problems["total"],
        )

    def test_planned_activities_are_not_completed(self) -> None:
        report = self._report(2026)
        planned = report["planned_activities"]
        self.assertGreaterEqual(len(planned), 1)
        self.assertLessEqual(len(planned), 7)
        today = date.today().isoformat()
        for item in planned:
            self.assertGreaterEqual(item["performed_on"], today)

    def test_yield_2025_and_2026_from_harvest_events(self) -> None:
        harvest_2025 = self._report(2025)["yield_summary"]
        harvest_2026 = self._report(2026)["yield_summary"]
        self.assertTrue(harvest_2025["recorded"])
        self.assertEqual(_money(harvest_2025["total_kg"]), Decimal("1850"))
        self.assertEqual(harvest_2025["harvest_events"], 1)
        if not harvest_2026["recorded"]:
            self.skipTest("Kusiljevo harvest seed nije primenjen")
        self.assertEqual(_money(harvest_2026["total_kg"]), Decimal("1420"))
        self.assertEqual(harvest_2026["harvest_events"], 3)
        self.assertEqual(harvest_2026["first_harvest_date"], "2026-09-10")
        self.assertEqual(harvest_2026["last_harvest_date"], "2026-09-20")
        yield_kpi = next(item for item in self._report(2026)["kpis"] if item["key"] == "yield_kg")
        self.assertTrue(yield_kpi["available"])
        self.assertEqual(_money(yield_kpi["value"]), Decimal("1420"))

    def test_year_over_year_2026_vs_2025(self) -> None:
        report = self._report(2026)
        self.assertTrue(report["parcel_summary"]["comparison_available"])
        self.assertEqual(report["parcel_summary"]["previous_year"], 2025)
        keys = {row["key"] for row in report["previous_year_comparison"]}
        self.assertIn("annual_cost", keys)
        self.assertIn("activities_completed", keys)
        cost_row = next(row for row in report["previous_year_comparison"] if row["key"] == "annual_cost")
        self.assertTrue(cost_row["change"]["available"])
        self.assertEqual(cost_row["change"]["tone"], "neutral")
        yield_row = next((row for row in report["previous_year_comparison"] if row["key"] == "yield_kg"), None)
        if yield_row is None:
            self.skipTest("Kusiljevo harvest seed nije primenjen")
        self.assertTrue(yield_row["change"]["available"])
        self.assertEqual(_money(yield_row["previous"]), Decimal("1850"))
        self.assertEqual(_money(yield_row["current"]), Decimal("1420"))

    def test_missing_previous_year_data(self) -> None:
        report = self._report(2022)
        self.assertFalse(report["parcel_summary"]["comparison_available"])
        self.assertEqual(report["previous_year_comparison"], [])
        cost_kpi = next(item for item in report["kpis"] if item["key"] == "annual_cost")
        self.assertFalse(cost_kpi["change"]["available"])

    def test_empty_parcel_distinguishes_missing_data(self) -> None:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json={
                "name": f"AT-report-empty-{uuid4().hex[:8]}",
                "area_hectares": 0.2,
                "row_count": 1,
                "trees_per_row": 2,
                "row_spacing_m": 5,
                "tree_spacing_m": 3.5,
                "planting_year": 2026,
                "starting_tree_number": 1,
                "varieties": DEFAULT_VARIETIES,
                "row_plan": [
                    {
                        "row_number": 1,
                        "variety": DEFAULT_VARIETIES[0]["name"],
                        "missing_positions": [],
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        parcel_id = created.json()["id"]
        try:
            report = self._report(2026, parcel_id)
            self.assertFalse(report["financial_summary"]["recorded"])
            self.assertFalse(report["financial_summary"]["annual_cost"]["available"])
            self.assertIsNone(report["financial_summary"]["annual_cost"]["value"])
            self.assertFalse(report["yield_summary"]["recorded"])
            self.assertIsNone(report["yield_summary"]["total_kg"])
            self.assertFalse(report["problem_summary"]["recorded"])
            self.assertFalse(report["parcel_summary"]["comparison_available"])
            self.assertEqual(report["planned_activities"], [])
            self.assertEqual(report["health_summary"]["total_trees"], 2)
        finally:
            deleted = self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)
            self.assertEqual(deleted.status_code, 204, deleted.text)

    def test_large_parcel_report_is_fast(self) -> None:
        started = perf_counter()
        report = self._report(2026)
        elapsed = perf_counter() - started
        self.assertGreaterEqual(report["health_summary"]["total_trees"], 1800)
        self.assertLess(elapsed, 4.0)
        self.assertTrue(report["executive_summary"])
        self.assertNotIn("TODO", report["executive_summary"])
