from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _money(value: str | int | float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


class SubsidyApiTests(TestCase):
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
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        cls.created_ids: list[str] = []

    @classmethod
    def tearDownClass(cls) -> None:
        for subsidy_id in cls.created_ids:
            cls.client.delete(f"/api/v1/subsidies/{subsidy_id}", headers=cls.headers)

    def _create(self, **overrides) -> dict:
        payload = {
            "title": f"Sistem za navodnjavanje {uuid4().hex[:8]}",
            "total_cost": 10000,
            "subsidy_amount": 4500,
            "received_on": date.today().isoformat(),
            "parcel_id": self.parcel["id"],
            "notes": "IPARD",
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/subsidies", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.created_ids.append(body["id"])
        return body

    def test_requires_auth(self) -> None:
        response = self.client.get("/api/v1/subsidies")
        self.assertEqual(response.status_code, 401)

    def test_create_computes_percent(self) -> None:
        created = self._create()
        self.assertEqual(_money(created["total_cost"]), Decimal("10000.00"))
        self.assertEqual(_money(created["subsidy_amount"]), Decimal("4500.00"))
        self.assertEqual(_money(created["subsidy_percent"]), Decimal("45.0"))
        self.assertEqual(created["parcel_id"], self.parcel["id"])
        self.assertEqual(created["parcel_name"], self.parcel["name"])

    def test_rejects_amount_greater_than_total(self) -> None:
        response = self.client.post(
            "/api/v1/subsidies",
            headers=self.headers,
            json={
                "title": "Prevelika subvencija",
                "total_cost": 1000,
                "subsidy_amount": 1001,
                "received_on": date.today().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_parcel_filter_and_farm_wide(self) -> None:
        farm_wide = self._create(parcel_id=None, title=f"Farm {uuid4().hex[:8]}")
        parcel_one = self._create()
        listed = self.client.get("/api/v1/subsidies", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        ids = {item["id"] for item in listed.json()}
        self.assertIn(farm_wide["id"], ids)
        self.assertIn(parcel_one["id"], ids)

        filtered = self.client.get(
            f"/api/v1/subsidies?parcel_id={self.parcel['id']}",
            headers=self.headers,
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        filtered_ids = {item["id"] for item in filtered.json()}
        self.assertIn(parcel_one["id"], filtered_ids)
        self.assertNotIn(farm_wide["id"], filtered_ids)

    def test_cost_summary_includes_subsidy_total(self) -> None:
        before = self.client.get("/api/v1/costs/summary", headers=self.headers)
        self.assertEqual(before.status_code, 200, before.text)
        previous = _money(before.json()["total_subsidies"])
        created = self._create(subsidy_amount=1234.50, total_cost=5000)
        after = self.client.get("/api/v1/costs/summary", headers=self.headers)
        self.assertEqual(after.status_code, 200, after.text)
        summary = after.json()
        self.assertEqual(_money(summary["total_subsidies"]), previous + Decimal("1234.50"))
        if _money(summary["total_costs"]) > 0:
            self.assertIsNotNone(summary["subsidy_percent_of_costs"])
        listed = self.client.get("/api/v1/subsidies", headers=self.headers)
        self.assertIn(created["id"], {item["id"] for item in listed.json()})

    def test_delete(self) -> None:
        created = self._create()
        response = self.client.delete(f"/api/v1/subsidies/{created['id']}", headers=self.headers)
        self.assertEqual(response.status_code, 204, response.text)
        self.created_ids.remove(created["id"])
        listed = self.client.get("/api/v1/subsidies", headers=self.headers)
        self.assertNotIn(created["id"], {item["id"] for item in listed.json()})
