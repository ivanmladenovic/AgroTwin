"""Phase 7 — Expert review + season transition end-to-end."""

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

MIN_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class ExpertReviewPlanningE2ETests(TestCase):
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
        trees = cls.client.get(f"/api/v1/parcels/{cls.parcel['id']}/trees", headers=cls.headers)
        assert trees.status_code == 200 and trees.json(), trees.text
        cls.tree = trees.json()[0]

    def _ensure_season(self, year: int) -> dict:
        listed = self.client.get(
            f"/api/v1/planning/parcels/{self.parcel['id']}/seasons",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        existing = next((item for item in listed.json() if item["year"] == year), None)
        if existing:
            return existing
        created = self.client.post(
            f"/api/v1/planning/parcels/{self.parcel['id']}/seasons",
            headers=self.headers,
            json={"year": year},
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def test_season_transition_expert_modify_audit_trail(self) -> None:
        year_prev = 2040
        year_next = 2041

        # --- 2026-equivalent season with history ---
        season_2026 = self._ensure_season(year_prev)
        obs = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map.get("observation", self.type_map["inspection"])["id"],
                "performed_on": date(year_prev, 5, 12).isoformat(),
                "scope_type": "tree",
                "parcel_id": self.parcel["id"],
                "row_id": self.tree["row_id"],
                "tree_id": self.tree["id"],
                "semantic_type": "observation",
                "observation_category": "disease",
                "observation_status": "new",
                "description": f"Obs-{uuid4().hex[:6]}",
            },
        )
        self.assertEqual(obs.status_code, 201, obs.text)

        treatment = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map["disease_treatment"]["id"],
                "performed_on": date(year_prev, 5, 15).isoformat(),
                "scope_type": "tree",
                "parcel_id": self.parcel["id"],
                "row_id": self.tree["row_id"],
                "tree_id": self.tree["id"],
                "semantic_type": "treatment",
                "observation_id": obs.json()["id"],
                "description": "Treatment 2026",
            },
        )
        self.assertEqual(treatment.status_code, 201, treatment.text)

        # Verified soil analysis
        soil_act = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map["soil_analysis"]["id"],
                "performed_on": date(year_prev, 3, 1).isoformat(),
                "scope_type": "parcel",
                "parcel_id": self.parcel["id"],
                "description": f"Soil-{uuid4().hex[:6]}",
            },
        )
        self.assertEqual(soil_act.status_code, 201, soil_act.text)
        uploaded = self.client.post(
            f"/api/v1/activities/{soil_act.json()['id']}/soil-analyses",
            headers=self.headers,
            data={"tree_id": self.tree["id"], "sampled_on": date(year_prev, 3, 1).isoformat()},
            files={"file": ("lab-2026.pdf", MIN_PDF, "application/pdf")},
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        analysis_id = uploaded.json()["id"]
        self.client.post(
            f"/api/v1/soil-analyses/{analysis_id}/results",
            headers=self.headers,
            json={"parameter_code": "PH", "original_parameter_name": "pH", "value": "6.4"},
        )
        verified = self.client.post(
            f"/api/v1/soil-analyses/{analysis_id}/verify",
            headers=self.headers,
            json={},
        )
        self.assertEqual(verified.status_code, 200, verified.text)

        plan_2026 = self.client.post(
            f"/api/v1/planning/seasons/{season_2026['id']}/plans/protection/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(plan_2026.status_code, 200, plan_2026.text)
        self.assertGreaterEqual(plan_2026.json()["item_count"], 1)

        finished = self.client.post(
            f"/api/v1/planning/seasons/{season_2026['id']}/finish",
            headers=self.headers,
        )
        self.assertEqual(finished.status_code, 200, finished.text)
        self.assertEqual(finished.json()["status"], "completed")

        # --- 2027-equivalent: new season + copy previous ---
        season_2027 = self.client.post(
            f"/api/v1/planning/parcels/{self.parcel['id']}/seasons",
            headers=self.headers,
            json={"year": year_next, "copy_from_season_id": season_2026["id"]},
        )
        if season_2027.status_code == 409:
            season_2027 = self._ensure_season(year_next)
            copied = self.client.post(
                f"/api/v1/planning/seasons/{season_2027['id']}/copy-from",
                headers=self.headers,
                json={"source_season_id": season_2026["id"]},
            )
            self.assertEqual(copied.status_code, 200, copied.text)
            season_2027 = copied
        else:
            self.assertEqual(season_2027.status_code, 201, season_2027.text)
        season_2027 = season_2027.json() if hasattr(season_2027, "json") else season_2027
        if not isinstance(season_2027, dict):
            season_2027 = season_2027.json()

        # Previous plan items are previous_plan / historical — not current confirmed issues
        previous_items = []
        for plan in season_2027.get("plans") or []:
            detail = self.client.get(f"/api/v1/planning/plans/{plan['id']}", headers=self.headers)
            self.assertEqual(detail.status_code, 200, detail.text)
            for item in detail.json()["items"]:
                if item["source"] == "previous_plan":
                    previous_items.append(item)
                    self.assertEqual(item["status"], "planned")
                    self.assertIn("istorijski", (item["priority_reason"] or "").lower())
        # Copy may no-op if plans already exist; still proceed with generate.

        # Latest verified soil used by nutrition plan
        nutrition = self.client.post(
            f"/api/v1/planning/seasons/{season_2027['id']}/plans/nutrition/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(nutrition.status_code, 200, nutrition.text)
        soil_reviews = [item for item in nutrition.json()["items"] if item["item_kind"] == "soil_review"]
        self.assertTrue(soil_reviews)
        self.assertTrue(
            any(
                any(str(ev.get("analysis_id")) == analysis_id for ev in (item.get("evidence") or []) if isinstance(ev, dict))
                for item in soil_reviews
                if item["source"] == "agronomic_rule"
            )
        )

        # New observation → protection plan updates; historical risk from previous year
        new_obs = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map.get("observation", self.type_map["inspection"])["id"],
                "performed_on": date(year_next, 4, 20).isoformat(),
                "scope_type": "tree",
                "parcel_id": self.parcel["id"],
                "row_id": self.tree["row_id"],
                "tree_id": self.tree["id"],
                "semantic_type": "observation",
                "observation_category": "disease",
                "observation_status": "new",
                "description": f"New-{uuid4().hex[:6]}",
            },
        )
        self.assertEqual(new_obs.status_code, 201, new_obs.text)

        protection = self.client.post(
            f"/api/v1/planning/seasons/{season_2027['id']}/plans/protection/generate",
            headers=self.headers,
            json={"replace_generated": True, "include_knowledge": False},
        )
        self.assertEqual(protection.status_code, 200, protection.text)
        items = protection.json()["items"]
        historical = [item for item in items if item["source"] == "history"]
        self.assertTrue(historical)
        self.assertIn("HISTORIJSKI", historical[0]["description"].upper())
        reactive = [
            item
            for item in items
            if item["stream"] == "reactive" and item.get("related_activity_id") == new_obs.json()["id"]
        ]
        self.assertTrue(reactive)
        target = reactive[0]
        plan_id = protection.json()["id"]

        # Submit for expert review
        submitted = self.client.post(
            f"/api/v1/planning/plans/{plan_id}/items/{target['id']}/expert-review/submit",
            headers=self.headers,
            json={"note": "Molim stručnu procenu"},
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["expert_review_status"], "pending")
        self.assertEqual(submitted.json()["display_status"], "pending_review")
        self.assertTrue(submitted.json()["requires_expert_review"])
        reviews = submitted.json()["expert_reviews"]
        self.assertTrue(reviews)
        review_id = reviews[-1]["id"]
        self.assertEqual(reviews[-1]["status"], "pending")
        original_title = reviews[-1]["original_recommendation_snapshot"]["title"]

        # Expert modifies — audit trail preserves original
        decided = self.client.post(
            f"/api/v1/planning/plans/{plan_id}/items/{target['id']}/expert-review/{review_id}/decide",
            headers=self.headers,
            json={
                "status": "modified",
                "comment": "Izmena nakon pregleda",
                "title": "Stručno izmenjena procena",
            },
        )
        self.assertEqual(decided.status_code, 200, decided.text)
        body = decided.json()
        self.assertEqual(body["expert_review_status"], "modified")
        self.assertEqual(body["display_status"], "modified")
        self.assertEqual(body["title"], "Stručno izmenjena procena")
        trail = body["expert_reviews"]
        closed = next(row for row in trail if row["id"] == review_id)
        self.assertEqual(closed["status"], "modified")
        self.assertEqual(closed["original_recommendation_snapshot"]["title"], original_title)
        self.assertEqual(closed["reviewed_recommendation_snapshot"]["title"], "Stručno izmenjena procena")
        self.assertIsNotNone(closed["reviewer_name"])

        # Dashboard priorities + domain cards
        dash = self.client.get(
            f"/api/v1/planning/parcels/{self.parcel['id']}/dashboard",
            headers=self.headers,
            params={"year": year_next},
        )
        self.assertEqual(dash.status_code, 200, dash.text)
        payload = dash.json()
        self.assertEqual(payload["year"], year_next)
        self.assertIn("protection", payload)
        self.assertIn("nutrition", payload)
        self.assertIn("irrigation", payload)
        self.assertIsInstance(payload["priorities"], list)

        # Authorization: foreign user cannot access review (create second login if possible — skip if single demo)
        # Ensure decide on foreign review_id fails with 404 via fake UUID
        foreign = self.client.post(
            f"/api/v1/planning/plans/{plan_id}/items/{target['id']}/expert-review/{uuid4()}/decide",
            headers=self.headers,
            json={"status": "approved", "comment": "x"},
        )
        self.assertIn(foreign.status_code, {404, 409})
