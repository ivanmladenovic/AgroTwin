"""API integration tests for the isolated map editor (non-destructive to rectangular flow)."""

from __future__ import annotations

import math
import os
from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.varieties import DEFAULT_VARIETIES
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app


def _rect(lon0: float, lat0: float, width_m: float, height_m: float) -> dict:
    m_lat = 111_320.0
    m_lon = 111_320.0 * math.cos(math.radians(lat0))
    dlon = width_m / m_lon
    dlat = height_m / m_lat
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon0, lat0],
                [lon0 + dlon, lat0],
                [lon0 + dlon, lat0 + dlat],
                [lon0, lat0 + dlat],
                [lon0, lat0],
            ]
        ],
    }


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class MapEditorApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("SATELLITE_PROVIDER", "fake")
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def test_preview_and_commit_boundary_without_replacing_trees(self) -> None:
        parcel_id = None
        try:
            created = self.client.post(
                "/api/v1/parcels",
                headers=self.headers,
                json={
                    "name": f"AT-map-{uuid4().hex[:8]}",
                    "area_hectares": 0.5,
                    "row_count": 3,
                    "trees_per_row": 4,
                    "row_spacing_m": 5,
                    "tree_spacing_m": 3.5,
                    "planting_year": 2023,
                    "starting_tree_number": 1,
                    "varieties": DEFAULT_VARIETIES,
                    "row_plan": [
                        {"row_number": i, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []}
                        for i in range(1, 4)
                    ],
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            parcel_id = created.json()["id"]
            twin_before = self.client.get(f"/api/v1/parcels/{parcel_id}/twin", headers=self.headers)
            self.assertEqual(twin_before.status_code, 200)
            tree_count_before = len(twin_before.json()["trees"])

            boundary = _rect(21.25, 44.75, 80.0, 50.0)
            metrics = self.client.post(
                f"/api/v1/parcels/{parcel_id}/map-editor/metrics",
                headers=self.headers,
                json={"boundary": boundary},
            )
            self.assertEqual(metrics.status_code, 200, metrics.text)
            self.assertGreater(metrics.json()["area_m2"], 3000)

            preview = self.client.post(
                f"/api/v1/parcels/{parcel_id}/map-editor/preview",
                headers=self.headers,
                json={
                    "boundary": boundary,
                    "config": {
                        "orientation_deg": 0,
                        "row_spacing_m": 5,
                        "tree_spacing_m": 4,
                        "first_row_offset_m": 2,
                        "row_end_offset_m": 1.5,
                        "tree_start_offset_m": None,
                        "boundary_buffer_m": 0,
                        "start_row_number": 1,
                        "number_rows_ascending": True,
                        "default_variety": DEFAULT_VARIETIES[0]["name"],
                        "default_planting_year": 2023,
                    },
                },
            )
            self.assertEqual(preview.status_code, 200, preview.text)
            body = preview.json()
            self.assertGreater(body["summary"]["tree_count"], 0)
            self.assertGreater(body["summary"]["row_count"], 0)

            commit = self.client.post(
                f"/api/v1/parcels/{parcel_id}/map-editor/commit",
                headers=self.headers,
                json={
                    "boundary": boundary,
                    "config": {
                        "orientation_deg": 0,
                        "row_spacing_m": 5,
                        "tree_spacing_m": 4,
                        "first_row_offset_m": 2,
                        "row_end_offset_m": 1.5,
                        "tree_start_offset_m": None,
                        "boundary_buffer_m": 0,
                        "start_row_number": 1,
                        "number_rows_ascending": True,
                        "default_variety": DEFAULT_VARIETIES[0]["name"],
                        "default_planting_year": 2023,
                    },
                    "replace_planting": False,
                    "create_missing_trees": False,
                    "remove_unmatched_trees": False,
                    "update_area_from_geometry": True,
                    "rows": body["rows"],
                    "trees": body["trees"],
                },
            )
            self.assertEqual(commit.status_code, 200, commit.text)
            self.assertEqual(commit.json()["trees_created"], 0)

            twin_after = self.client.get(f"/api/v1/parcels/{parcel_id}/twin", headers=self.headers)
            self.assertEqual(twin_after.status_code, 200)
            self.assertEqual(len(twin_after.json()["trees"]), tree_count_before)
            self.assertIsNotNone(twin_after.json()["parcel"]["boundary"])

            state = self.client.get(f"/api/v1/parcels/{parcel_id}/map-editor", headers=self.headers)
            self.assertEqual(state.status_code, 200, state.text)
            self.assertTrue(state.json()["has_geographic_boundary"])

            # Existing rectangular canvas twin still loads
            self.assertGreater(twin_after.json()["stats"]["total_trees"], 0)
        finally:
            if parcel_id:
                self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)

    def test_create_parcel_from_map_editor(self) -> None:
        parcel_id = None
        try:
            boundary = _rect(21.3, 44.78, 60.0, 40.0)
            created = self.client.post(
                "/api/v1/map-editor/parcels",
                headers=self.headers,
                json={
                    "name": f"AT-geo-{uuid4().hex[:8]}",
                    "boundary": boundary,
                    "config": {
                        "orientation_deg": 90,
                        "row_spacing_m": 4.5,
                        "tree_spacing_m": 3.5,
                        "first_row_offset_m": 2,
                        "row_end_offset_m": 1,
                        "tree_start_offset_m": None,
                        "boundary_buffer_m": 0,
                        "start_row_number": 1,
                        "number_rows_ascending": True,
                        "default_variety": DEFAULT_VARIETIES[0]["name"],
                        "default_planting_year": 2025,
                    },
                    "commit_planting": True,
                },
            )
            self.assertEqual(created.status_code, 200, created.text)
            data = created.json()
            parcel_id = data["parcel_id"]
            self.assertTrue(data["has_geographic_boundary"])
            self.assertGreater(len(data["trees"]), 0)
            # Trees should have geographic positions
            self.assertTrue(any(t["has_geographic_position"] for t in data["trees"]))
        finally:
            if parcel_id:
                self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)
