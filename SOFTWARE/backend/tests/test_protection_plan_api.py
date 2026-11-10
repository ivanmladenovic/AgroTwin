"""Phase 5 — Protection Plan Engine foundation tests."""

from __future__ import annotations

from datetime import date
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


class ProtectionPlanApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        assert parcels.status_code == 200, parcels.text
        payload = parcels.json()
        assert payload, "Nema parcela"
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        types = cls.client.get("/api/v1/activity-types", headers=cls.headers)
        assert types.status_code == 200, types.text
        cls.type_map = {item["slug"]: item for item in types.json()}
        rows = cls.client.get(f"/api/v1/parcels/{cls.parcel['id']}/rows", headers=cls.headers)
        assert rows.status_code == 200 and rows.json(), rows.text
        cls.row = rows.json()[0]
        trees = cls.client.get(f"/api/v1/parcels/{cls.parcel['id']}/trees", headers=cls.headers)
        assert trees.status_code == 200 and trees.json(), trees.text
        cls.tree = next((item for item in trees.json() if item["row_id"] == cls.row["id"]), trees.json()[0])
        other_parcels = [item for item in payload if item["id"] != cls.parcel["id"]]
        cls.other_parcel = other_parcels[0] if other_parcels else None

    def _ensure_season(self, year: int, parcel_id: str | None = None) -> dict:
        parcel_id = parcel_id or self.parcel["id"]
        listed = self.client.get(f"/api/v1/planning/parcels/{parcel_id}/seasons", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        existing = next((item for item in listed.json() if item["year"] == year), None)
        if existing:
            return existing
        created = self.client.post(
            f"/api/v1/planning/parcels/{parcel_id}/seasons",
            headers=self.headers,
            json={"year": year},
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def _create_observation(
        self,
        *,
        year: int,
        scope: str = "tree",
        parcel_id: str | None = None,
        description: str | None = None,
    ) -> dict:
        parcel_id = parcel_id or self.parcel["id"]
        body = {
            "activity_type_id": self.type_map.get("observation", self.type_map["inspection"])["id"],
            "performed_on": date(year, 5, 14).isoformat(),
            "scope_type": "parcel",
            "parcel_id": parcel_id,
            "description": description or f"Obs-{uuid4().hex[:6]}",
            "semantic_type": "observation",
            "observation_category": "disease",
            "observation_status": "new",
        }
        if scope == "row":
            body.update({"scope_type": "row", "row_id": self.row["id"], "row_ids": [self.row["id"]]})
        if scope == "tree":
            body.update(
                {
                    "scope_type": "tree",
                    "row_id": self.tree["row_id"],
                    "tree_id": self.tree["id"],
                }
            )
        response = self.client.post("/api/v1/activities", headers=self.headers, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_generate_protection_plan_preventive_and_reactive(self) -> None:
        year = 2027
        prev_year = 2026
        self._ensure_season(prev_year)
        # Historical observation (previous year) + current observation on tree 37-equivalent.
        historical = self._create_observation(year=prev_year, scope="tree", description="Previous disease observation")
        # Previous treatment — must not become "current".
        treatment = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map["disease_treatment"]["id"],
                "performed_on": date(prev_year, 5, 18).isoformat(),
                "scope_type": "tree",
                "parcel_id": self.parcel["id"],
                "row_id": self.tree["row_id"],
                "tree_id": self.tree["id"],
                "semantic_type": "treatment",
                "observation_id": historical["id"],
                "description": "Previous treatment",
            },
        )
        self.assertEqual(treatment.status_code, 201, treatment.text)
        current = self._create_observation(year=year, scope="tree", description="Current observation")

        # Unrelated row observation should not pull unrelated scopes into current reactive items wrongly —
        # create on parcel only for noise.
        noise = self._create_observation(year=year, scope="parcel", description="Parcel noise")

        season = self._ensure_season(year)
        generated = self.client.post(
            f"/api/v1/planning/seasons/{season['id']}/plans/protection/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        plan = generated.json()
        self.assertEqual(plan["type"], "protection")
        self.assertGreaterEqual(plan["item_count"], 1)
        items = plan["items"]

        # Historical appears as HISTORY / monitoring, not as current confirmed disease.
        historical_items = [item for item in items if item["source"] == "history"]
        self.assertTrue(historical_items)
        for item in historical_items:
            self.assertEqual(item["item_kind"], "monitoring")
            self.assertEqual(item["stream"], "preventive")
            self.assertIn("HISTORIJSKI", item["description"].upper())
            self.assertNotEqual(item["status"], "approved")

        # Current observation → reactive assessment with provenance.
        reactive = [
            item
            for item in items
            if item["stream"] == "reactive" and item.get("related_activity_id") == current["id"]
        ]
        self.assertTrue(reactive)
        for item in reactive:
            self.assertIn(item["item_kind"], {"assessment", "expert_review"})
            self.assertTrue(item["reason"])
            self.assertTrue(item["priority_reason"])
            self.assertIn(item["priority_level"], {"high", "medium", "low", "info"})
            # Must not claim disease confirmed.
            blob = f"{item['title']} {item['description']}".lower()
            self.assertNotIn("potvrđena bolest", blob)

        # Previous treatment must not be interpreted as current fact item.
        for item in items:
            if item.get("related_activity_id") == treatment.json()["id"]:
                self.fail("Previous treatment should not create a current related plan item")

        # Unrelated parcel excluded when we have other parcel.
        if self.other_parcel:
            other_season = self._ensure_season(year, parcel_id=self.other_parcel["id"])
            other_plan = self.client.post(
                f"/api/v1/planning/seasons/{other_season['id']}/plans/protection/generate",
                headers=self.headers,
                json={"replace_generated": True, "include_knowledge": False},
            )
            self.assertEqual(other_plan.status_code, 200, other_plan.text)
            other_ids = {item.get("related_activity_id") for item in other_plan.json()["items"]}
            self.assertNotIn(current["id"], other_ids)
            self.assertNotIn(noise["id"], other_ids)

        # Provenance fields present on generated items.
        for item in items:
            self.assertIn("source", item)
            self.assertIn("item_kind", item)
            self.assertIn("stream", item)
            self.assertIn("priority_level", item)

    def test_insufficient_data_negative_path(self) -> None:
        # Use a high year with no observations; engine still returns monitoring / info without pesticide recs.
        year = 2098
        season = self._ensure_season(year)
        generated = self.client.post(
            f"/api/v1/planning/seasons/{season['id']}/plans/protection/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        items = generated.json()["items"]
        self.assertTrue(items)
        titles = " ".join(item["title"] for item in items).lower()
        descriptions = " ".join((item["description"] or "") for item in items).lower()
        blob = titles + " " + descriptions
        # Disallow product recommendations; mentioning that there is no pesticide advice is OK.
        self.assertNotIn("preporučeni pesticid", blob)
        self.assertNotIn("primeniti pesticid", blob)
        self.assertFalse(any(item["item_kind"] == "intervention_pending" for item in items))

    def test_generate_does_not_wipe_user_items(self) -> None:
        year = 2028
        season = self._ensure_season(year)
        first = self.client.post(
            f"/api/v1/planning/seasons/{season['id']}/plans/protection/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(first.status_code, 200, first.text)
        plan_id = first.json()["id"]
        user_item = self.client.post(
            f"/api/v1/planning/plans/{plan_id}/items",
            headers=self.headers,
            json={
                "title": "User note",
                "description": "Keep me",
                "source": "user",
                "item_kind": "monitoring",
            },
        )
        self.assertEqual(user_item.status_code, 201, user_item.text)
        user_id = user_item.json()["id"]
        second = self.client.post(
            f"/api/v1/planning/seasons/{season['id']}/plans/protection/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(second.status_code, 200, second.text)
        ids = {item["id"] for item in second.json()["items"]}
        self.assertIn(user_id, ids)
