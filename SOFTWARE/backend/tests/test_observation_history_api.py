"""Observation / semantic activity history for planning (Phase 4)."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from uuid import UUID, uuid4
import sys

from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.db.session import SessionLocal
from app.main import app
from app.models.activity import Activity
from app.models.enums import ObservationStatus
from app.models.farm import Farm
from app.services.activity import ActivityService


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _png_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color=(40, 120, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ObservationHistoryApiTests(TestCase):
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
        cls.tree = trees.json()[0]

    def _create(self, **overrides) -> dict:
        body = {
            "activity_type_id": self.type_map.get("observation", self.type_map["inspection"])["id"],
            "performed_on": date.today().isoformat(),
            "scope_type": "parcel",
            "parcel_id": self.parcel["id"],
            "description": f"Obs-{uuid4().hex[:8]}",
            "semantic_type": "observation",
            "observation_category": "unknown",
            "observation_status": "new",
            "status": "completed",
        }
        body.update(overrides)
        response = self.client.post("/api/v1/activities", headers=self.headers, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_observation_parcel_row_tree_scopes(self) -> None:
        parcel_obs = self._create(scope_type="parcel", description="Parcel observation")
        self.assertEqual(parcel_obs["scope_type"], "parcel")
        self.assertEqual(parcel_obs["semantic_type"], "observation")
        self.assertEqual(parcel_obs["observation_category"], "unknown")
        self.assertEqual(parcel_obs["observation_status"], "new")
        self.assertIsNone(parcel_obs["row_id"])
        self.assertIsNone(parcel_obs["tree_id"])

        row_obs = self._create(
            scope_type="row",
            row_id=self.row["id"],
            row_ids=[self.row["id"]],
            description="Row observation",
            observation_category="leaf",
        )
        self.assertEqual(row_obs["scope_type"], "row")
        self.assertEqual(row_obs["row_id"], self.row["id"])
        self.assertIsNone(row_obs["tree_id"])
        self.assertEqual(row_obs["observation_category"], "leaf")

        tree_obs = self._create(
            scope_type="tree",
            row_id=self.tree["row_id"],
            tree_id=self.tree["id"],
            description="Tree observation",
            observation_category="pest",
            observation_severity="high",
        )
        self.assertEqual(tree_obs["scope_type"], "tree")
        self.assertEqual(tree_obs["tree_id"], self.tree["id"])
        self.assertEqual(tree_obs["row_id"], self.tree["row_id"])
        self.assertEqual(tree_obs["observation_category"], "pest")
        listed = self.client.get(
            f"/api/v1/activities?parcel_id={self.parcel['id']}&tree_id={self.tree['id']}",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        matches = [item for item in listed.json() if item["id"] == tree_obs["id"]]
        self.assertEqual(len(matches), 1)

    def test_photo_attachment_on_activity_observation(self) -> None:
        obs = self._create(description="With photo")
        upload = self.client.post(
            "/api/v1/photos",
            headers=self.headers,
            data={"entity_type": "activity", "entity_id": obs["id"], "caption": "list"},
            files={"file": ("list.png", _png_bytes(), "image/png")},
        )
        self.assertEqual(upload.status_code, 201, upload.text)
        self.assertEqual(upload.json()["entity_type"], "activity")
        self.assertEqual(upload.json()["entity_id"], obs["id"])

        detail = self.client.get(f"/api/v1/activities/{obs['id']}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(len(detail.json()["photos"]), 1)
        self.assertEqual(detail.json()["photos"][0]["caption"], "list")

    def test_treatment_link_and_follow_up(self) -> None:
        obs = self._create(description="Initial problem", observation_category="disease")
        treatment = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map["disease_treatment"]["id"],
                "performed_on": date.today().isoformat(),
                "scope_type": "parcel",
                "parcel_id": self.parcel["id"],
                "description": "Spray after observation",
                "semantic_type": "treatment",
                "observation_id": obs["id"],
            },
        )
        self.assertEqual(treatment.status_code, 201, treatment.text)
        self.assertEqual(treatment.json()["semantic_type"], "treatment")
        self.assertEqual(treatment.json()["observation_id"], obs["id"])

        follow = self._create(
            description="Follow-up check",
            semantic_type="observation",
            observation_category="disease",
            observation_status="monitoring",
            follow_up_of_id=treatment.json()["id"],
        )
        self.assertEqual(follow["follow_up_of_id"], treatment.json()["id"])

        irrigation = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map["irrigation"]["id"],
                "performed_on": date.today().isoformat(),
                "scope_type": "parcel",
                "parcel_id": self.parcel["id"],
                "description": f"Compat-{uuid4().hex[:6]}",
                "line_items": [{"name": "Nafta", "quantity": 1, "unit": "L", "amount": 2}],
            },
        )
        self.assertEqual(irrigation.status_code, 201, irrigation.text)
        self.assertEqual(irrigation.json()["semantic_type"], "irrigation")
        self.assertIsNone(irrigation.json()["observation_category"])

    def test_unknown_diagnosis_and_ai_cannot_confirm(self) -> None:
        obs = self._create(observation_category="unknown", observation_status="new")
        self.assertEqual(obs["observation_category"], "unknown")

        db = SessionLocal()
        try:
            activity_id = UUID(obs["id"])
            activity = db.get(Activity, activity_id)
            assert activity is not None
            farm = db.get(Farm, activity.farm_id)
            assert farm is not None
            service = ActivityService(db)
            with self.assertRaises(AppError) as ctx:
                service.apply_ai_observation_hint(
                    activity_id,
                    farm.owner_id,
                    status=ObservationStatus.CONFIRMED,
                )
            self.assertEqual(ctx.exception.code, "ai_cannot_confirm")
        finally:
            db.close()

        confirmed = self.client.patch(
            f"/api/v1/activities/{obs['id']}",
            headers=self.headers,
            json={"observation_status": "confirmed"},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["observation_status"], "confirmed")

    def test_authorization_blocks_foreign_link(self) -> None:
        bad = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map["disease_treatment"]["id"],
                "performed_on": date.today().isoformat(),
                "scope_type": "parcel",
                "parcel_id": self.parcel["id"],
                "semantic_type": "treatment",
                "observation_id": str(uuid4()),
            },
        )
        self.assertIn(bad.status_code, {404, 422}, bad.text)
