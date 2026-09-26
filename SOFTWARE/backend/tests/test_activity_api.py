from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
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


class ActivityLineItemApiTests(TestCase):
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
        types = cls.client.get("/api/v1/activity-types", headers=cls.headers)
        if types.status_code != 200:
            raise AssertionError(types.text)
        cls.type_map = {item["slug"]: item for item in types.json()}

    def _create(self, slug: str, line_items: list[dict[str, Any]]) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map[slug]["id"],
                "performed_on": date.today().isoformat(),
                "scope_type": "parcel",
                "parcel_id": self.parcel["id"],
                "description": f"AT-line-{slug}-{uuid4().hex[:8]}",
                "line_items": line_items,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_irrigation_stores_diesel_and_equipment_costs(self) -> None:
        created = self._create(
            "irrigation",
            [
                {"name": "Nafta", "quantity": 12, "unit": "L", "amount": 45.5},
                {"name": "Kap po kap crevo", "quantity": 200, "unit": "m", "amount": 80},
            ],
        )
        self.assertEqual(_money(created["quantity"]), Decimal("12"))
        self.assertEqual(created["unit"], "L")
        self.assertEqual(len(created["line_items"]), 2)
        fuel, equipment = created["line_items"]
        self.assertEqual(fuel["name"], "Nafta")
        self.assertEqual(_money(fuel["quantity"]), Decimal("12"))
        self.assertEqual(_money(fuel["amount"]), Decimal("45.50"))
        self.assertEqual(equipment["name"], "Kap po kap crevo")
        self.assertEqual(equipment["unit"], "m")
        self.assertEqual(_money(created["total_cost"]), Decimal("125.50"))
        slugs = {cost["description"]: cost["cost_category"]["slug"] for cost in created["costs"]}
        self.assertEqual(slugs["Nafta"], "fuel")
        self.assertEqual(slugs["Kap po kap crevo"], "equipment")

    def test_spraying_stores_preparations_and_protection_costs(self) -> None:
        created = self._create(
            "spraying",
            [
                {"name": "Cuproxat", "quantity": 2, "unit": "L", "amount": 30},
                {"name": "Sumpor", "quantity": 1.5, "unit": "kg", "amount": 18},
            ],
        )
        self.assertEqual(len(created["line_items"]), 2)
        self.assertEqual(created["line_items"][0]["name"], "Cuproxat")
        self.assertEqual(created["line_items"][1]["unit"], "kg")
        self.assertEqual(_money(created["total_cost"]), Decimal("48.00"))
        slugs = {cost["cost_category"]["slug"] for cost in created["costs"]}
        self.assertEqual(slugs, {"plant_protection"})

    def test_fertilization_stores_weight_and_fertilizer_cost(self) -> None:
        created = self._create(
            "fertilization",
            [{"name": "NPK 15-15-15", "quantity": 25, "unit": "kg", "amount": 80}],
        )
        item = created["line_items"][0]
        self.assertEqual(item["name"], "NPK 15-15-15")
        self.assertEqual(item["unit"], "kg")
        self.assertEqual(_money(item["quantity"]), Decimal("25"))
        self.assertEqual(_money(created["total_cost"]), Decimal("80.00"))
        self.assertEqual(created["costs"][0]["cost_category"]["slug"], "fertilizers")

    def test_other_activity_stores_name_quantity_and_price(self) -> None:
        created = self._create(
            "pruning",
            [{"name": "Sezonska rezidba", "quantity": 6, "unit": "sati", "amount": 90}],
        )
        item = created["line_items"][0]
        self.assertEqual(item["name"], "Sezonska rezidba")
        self.assertEqual(item["unit"], "sati")
        self.assertEqual(_money(created["total_cost"]), Decimal("90.00"))
        self.assertEqual(created["costs"][0]["cost_category"]["slug"], "other")
