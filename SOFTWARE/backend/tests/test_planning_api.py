from __future__ import annotations

from datetime import date
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


def _parcel_payload(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "area_hectares": 0.4,
        "row_count": 2,
        "trees_per_row": 2,
        "row_spacing_m": 5,
        "tree_spacing_m": 3.5,
        "planting_year": 2024,
        "starting_tree_number": 1,
        "varieties": DEFAULT_VARIETIES,
        "row_plan": [
            {"row_number": 1, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []},
            {"row_number": 2, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []},
        ],
    }


class PlanningApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def _create_parcel(self) -> dict[str, Any]:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json=_parcel_payload(f"AT-plan-{uuid4().hex[:8]}"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def _create_season(self, parcel_id: str, year: int, **extra: Any) -> dict[str, Any]:
        payload = {"year": year, **extra}
        response = self.client.post(
            f"/api/v1/planning/parcels/{parcel_id}/seasons",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_season_plan_and_item_bound_to_parcel(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        season = self._create_season(parcel_id, 2027)
        self.assertEqual(season["parcel_id"], parcel_id)
        self.assertEqual(season["year"], 2027)
        self.assertEqual(season["status"], "draft")

        plan_response = self.client.post(
            f"/api/v1/planning/seasons/{season['id']}/plans",
            headers=self.headers,
            json={"type": "protection"},
        )
        self.assertEqual(plan_response.status_code, 201, plan_response.text)
        plan = plan_response.json()
        self.assertEqual(plan["type"], "protection")
        self.assertEqual(plan["status"], "draft")
        self.assertEqual(plan["planning_season_id"], season["id"])

        item_response = self.client.post(
            f"/api/v1/planning/plans/{plan['id']}/items",
            headers=self.headers,
            json={
                "scope_type": "parcel",
                "title": "Pregled pupoljaka",
                "description": "Osnovni monitoring",
                "planned_date_from": "2027-03-01",
                "planned_date_to": "2027-03-15",
            },
        )
        self.assertEqual(item_response.status_code, 201, item_response.text)
        item = item_response.json()
        self.assertEqual(item["scope_id"], parcel_id)
        self.assertEqual(item["source"], "user")
        self.assertEqual(item["status"], "planned")

        detail = self.client.get(f"/api/v1/planning/plans/{plan['id']}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["item_count"], 1)

    def test_create_new_season_and_copy_previous_with_provenance(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        season_2026 = self._create_season(parcel_id, 2026)
        plan = self.client.post(
            f"/api/v1/planning/seasons/{season_2026['id']}/plans",
            headers=self.headers,
            json={"type": "nutrition"},
        ).json()
        source_item = self.client.post(
            f"/api/v1/planning/plans/{plan['id']}/items",
            headers=self.headers,
            json={
                "title": "Prolećna prihrana",
                "planned_date_from": "2026-04-10",
                "planned_date_to": "2026-04-20",
                "priority": 2,
            },
        ).json()

        season_2027 = self._create_season(
            parcel_id,
            2027,
            copy_from_season_id=season_2026["id"],
        )
        self.assertEqual(season_2027["copied_from_season_id"], season_2026["id"])
        self.assertEqual(len(season_2027["plans"]), 1)
        copied_plan_id = season_2027["plans"][0]["id"]
        detail = self.client.get(f"/api/v1/planning/plans/{copied_plan_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        items = detail.json()["items"]
        self.assertEqual(len(items), 1)
        copied = items[0]
        self.assertEqual(copied["source"], "previous_plan")
        self.assertEqual(copied["source_season_id"], season_2026["id"])
        self.assertEqual(copied["source_plan_id"], plan["id"])
        self.assertEqual(copied["source_plan_item_id"], source_item["id"])
        self.assertEqual(copied["status"], "planned")
        self.assertEqual(copied["expert_review_status"], "pending")
        self.assertEqual(copied["planned_date_from"], "2027-04-10")
        self.assertEqual(copied["planned_date_to"], "2027-04-20")

    def test_copy_from_empty_previous_season(self) -> None:
        parcel = self._create_parcel()
        parcel_id = parcel["id"]
        empty_2026 = self._create_season(parcel_id, 2026)
        season_2027 = self._create_season(parcel_id, 2027)
        response = self.client.post(
            f"/api/v1/planning/seasons/{season_2027['id']}/copy-from",
            headers=self.headers,
            json={"source_season_id": empty_2026["id"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["copied_from_season_id"], empty_2026["id"])
        self.assertEqual(body["plans"], [])

    def test_foreign_parcel_is_hidden(self) -> None:
        response = self.client.get(
            f"/api/v1/planning/parcels/{uuid4()}/summary",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            f"/api/v1/planning/parcels/{uuid4()}/seasons",
            headers=self.headers,
            json={"year": 2028},
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            f"/api/v1/planning/seasons/{uuid4()}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.get(f"/api/v1/planning/parcels/{uuid4()}/seasons")
        self.assertEqual(response.status_code, 401)

    def test_duplicate_season_year_is_rejected(self) -> None:
        parcel = self._create_parcel()
        self._create_season(parcel["id"], 2030)
        response = self.client.post(
            f"/api/v1/planning/parcels/{parcel['id']}/seasons",
            headers=self.headers,
            json={"year": 2030},
        )
        self.assertEqual(response.status_code, 409, response.text)

    def test_ai_item_cannot_be_auto_approved(self) -> None:
        parcel = self._create_parcel()
        season = self._create_season(parcel["id"], 2031)
        plan = self.client.post(
            f"/api/v1/planning/seasons/{season['id']}/plans",
            headers=self.headers,
            json={"type": "irrigation"},
        ).json()
        response = self.client.post(
            f"/api/v1/planning/plans/{plan['id']}/items",
            headers=self.headers,
            json={
                "title": "AI predlog",
                "source": "ai",
                "status": "approved",
            },
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_parcel_summary_lists_seasons(self) -> None:
        parcel = self._create_parcel()
        self._create_season(parcel["id"], 2025)
        response = self.client.get(
            f"/api/v1/planning/parcels/{parcel['id']}/summary",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["parcel_id"], parcel["id"])
        self.assertEqual(len(body["seasons"]), 1)
        self.assertIn("organic_status_note", body)
        self.assertEqual(body["organic_status"], "Konvencionalna")
