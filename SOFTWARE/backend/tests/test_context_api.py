from __future__ import annotations

from datetime import date
from pathlib import Path
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


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class ContextApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        if parcels.status_code != 200 or not parcels.json():
            raise AssertionError("Nema parcela za context testove")
        cls.parcel = next((item for item in parcels.json() if item["name"] == "Kusiljevo"), parcels.json()[0])
        rows = cls.client.get(f"/api/v1/parcels/{cls.parcel['id']}/rows", headers=cls.headers)
        cls.row = rows.json()[0] if rows.status_code == 200 and rows.json() else None
        trees = cls.client.get(f"/api/v1/parcels/{cls.parcel['id']}/trees", headers=cls.headers)
        cls.tree = trees.json()[0] if trees.status_code == 200 and trees.json() else None
        other = next((item for item in parcels.json() if item["id"] != cls.parcel["id"]), None)
        cls.other_parcel = other
        other_tree = None
        if other:
            other_trees = cls.client.get(f"/api/v1/parcels/{other['id']}/trees", headers=cls.headers)
            if other_trees.status_code == 200 and other_trees.json():
                other_tree = other_trees.json()[0]
        cls.other_tree = other_tree

    def _build(self, payload: dict, debug: bool = False):
        path = "/api/v1/context/preview" if debug else "/api/v1/context/build"
        return self.client.post(path, headers=self.headers, json=payload)

    def test_unauthenticated_request_is_rejected(self) -> None:
        response = self.client.post("/api/v1/context/build", json={"request_type": "PHOTO_ANALYSIS", "parcel_id": self.parcel["id"]})
        self.assertEqual(response.status_code, 401)

    def test_unknown_parcel_is_not_found(self) -> None:
        response = self._build({"request_type": "PARCEL_ANALYSIS", "parcel_id": str(uuid4())})
        self.assertEqual(response.status_code, 404)

    def test_unknown_tree_is_not_found(self) -> None:
        response = self._build({"request_type": "PHOTO_ANALYSIS", "tree_id": str(uuid4())})
        self.assertEqual(response.status_code, 404)

    def test_unknown_photo_is_not_found(self) -> None:
        response = self._build({"request_type": "PHOTO_ANALYSIS", "photo_id": str(uuid4())})
        self.assertEqual(response.status_code, 404)

    def test_tree_from_another_parcel_is_rejected(self) -> None:
        if not self.tree:
            self.skipTest("Nema stabala")
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json={
                "name": f"AT-ctx-{uuid4().hex[:8]}",
                "area_hectares": 0.2,
                "row_count": 1,
                "trees_per_row": 1,
                "row_spacing_m": 5,
                "tree_spacing_m": 3.5,
                "planting_year": 2024,
                "starting_tree_number": 1,
                "varieties": DEFAULT_VARIETIES,
                "row_plan": [{"row_number": 1, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []}],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        other_id = created.json()["id"]
        try:
            response = self._build(
                {
                    "request_type": "PHOTO_ANALYSIS",
                    "parcel_id": other_id,
                    "tree_id": self.tree["id"],
                }
            )
            self.assertEqual(response.status_code, 400)
        finally:
            self.client.delete(f"/api/v1/parcels/{other_id}", headers=self.headers)

    def test_photo_analysis_for_parcel(self) -> None:
        response = self._build(
            {
                "request_type": "PHOTO_ANALYSIS",
                "parcel_id": self.parcel["id"],
                "query": "Šta se dešava sa listovima?",
            }
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["context_version"], "1.0")
        self.assertEqual(body["request"]["type"], "PHOTO_ANALYSIS")
        self.assertEqual(body["subject"]["type"], "PARCEL")
        self.assertEqual(body["subject"]["parcel"]["id"], self.parcel["id"])
        self.assertIsNone(body["costs"])
        self.assertIsNone(body["harvest"])
        if body["soil"] is not None:
            self.assertEqual(body["soil"]["source_type"], "modeled_estimate")
        self.assertIn("data_quality", body)
        self.assertIn("warnings", body)
        self.assertIn("provenance", body)

    def test_tree_request_resolves_hierarchy(self) -> None:
        if not self.tree:
            self.skipTest("Nema stabala")
        response = self._build({"request_type": "PROBLEM_ANALYSIS", "tree_id": self.tree["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["subject"]["type"], "TREE")
        self.assertEqual(body["subject"]["tree"]["id"], self.tree["id"])
        self.assertEqual(body["subject"]["parcel"]["id"], self.parcel["id"])
        self.assertIsNotNone(body["subject"]["row"])
        self.assertIsNotNone(body["subject"]["farm"])

    def test_row_request_resolves_parcel_and_farm(self) -> None:
        if not self.row:
            self.skipTest("Nema redova")
        response = self._build({"request_type": "PARCEL_ANALYSIS", "row_id": self.row["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["subject"]["type"], "ROW")
        self.assertIsNone(body["subject"]["tree"])
        self.assertEqual(body["subject"]["parcel"]["id"], self.parcel["id"])

    def test_all_profiles_return_structured_context(self) -> None:
        types = [
            "PHOTO_ANALYSIS",
            "PROBLEM_ANALYSIS",
            "PARCEL_ANALYSIS",
            "SEASON_ANALYSIS",
            "ACTIVITY_ANALYSIS",
        ]
        payload = {"parcel_id": self.parcel["id"], "season_year": date.today().year}
        if self.tree:
            payload["tree_id"] = self.tree["id"]
        activities = self.client.get("/api/v1/activities", headers=self.headers, params={"parcel_id": self.parcel["id"]})
        activity_id = None
        if activities.status_code == 200 and activities.json():
            activity_id = activities.json()[0]["id"]
        for request_type in types:
            body_in = {**payload, "request_type": request_type}
            if request_type == "ACTIVITY_ANALYSIS":
                if not activity_id:
                    continue
                body_in["activity_id"] = activity_id
            response = self._build(body_in)
            self.assertEqual(response.status_code, 200, f"{request_type}: {response.text}")
            body = response.json()
            self.assertEqual(body["context_version"], "1.0")
            self.assertEqual(body["request"]["type"], request_type)
            self.assertIn("warnings", body)

    def test_preview_includes_debug_records(self) -> None:
        response = self._build({"request_type": "PARCEL_ANALYSIS", "parcel_id": self.parcel["id"]}, debug=True)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIsNotNone(body["debug"])
        self.assertIn("providers_used", body["debug"])
        self.assertIn("records", body["debug"])
        self.assertGreater(len(body["debug"]["providers_used"]), 0)

    def test_season_analysis_includes_cost_summary(self) -> None:
        response = self._build({"request_type": "SEASON_ANALYSIS", "parcel_id": self.parcel["id"], "season_year": date.today().year})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIsNotNone(body["costs"])
        self.assertIn(body["costs"]["status"], {"AVAILABLE", "MISSING"})

    def test_soil_never_looks_like_lab_analysis(self) -> None:
        response = self._build({"request_type": "PARCEL_ANALYSIS", "parcel_id": self.parcel["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        soil = response.json()["soil"]
        self.assertIsNotNone(soil)
        self.assertEqual(soil["source"], "SoilGrids")
        self.assertEqual(soil["source_type"], "modeled_estimate")
        self.assertTrue(soil["is_modeled"])

    def test_activity_scope_is_preserved(self) -> None:
        response = self._build({"request_type": "PHOTO_ANALYSIS", "parcel_id": self.parcel["id"]}, debug=True)
        self.assertEqual(response.status_code, 200, response.text)
        for item in response.json()["activities"]:
            self.assertIn(item["scope"], {"FARM", "PARCEL", "ROW", "TREE"})
            self.assertIn("relevance_score", item)
            self.assertIn("temporal_relation", item)
            self.assertEqual(item["provenance"]["source_type"], "user_record")

    def test_soil_failure_does_not_destroy_context(self) -> None:
        with patch("app.context.engine.SoilContextProvider.collect", side_effect=RuntimeError("soil down")):
            response = self._build({"request_type": "PARCEL_ANALYSIS", "parcel_id": self.parcel["id"]}, debug=True)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["subject"]["parcel"]["id"], self.parcel["id"])
        self.assertEqual(body["data_quality"]["soil"], "ERROR")
        self.assertTrue(any(item["source"] == "soil" for item in body["warnings"]))
        self.assertTrue(any(item["source"] == "soil" for item in body["debug"]["provider_failures"]))

    def test_weather_failure_does_not_destroy_context(self) -> None:
        with patch("app.context.engine.WeatherContextProvider.collect", side_effect=RuntimeError("weather down")):
            response = self._build({"request_type": "PHOTO_ANALYSIS", "parcel_id": self.parcel["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["data_quality"]["weather"], "ERROR")
        self.assertTrue(any(item["source"] == "weather" for item in body["warnings"]))
        self.assertIsNotNone(body["subject"]["parcel"])

