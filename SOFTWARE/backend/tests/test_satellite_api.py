from __future__ import annotations

import os
from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.config import reload_settings
from app.core.varieties import DEFAULT_VARIETIES
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app
from app.satellite.providers.factory import reload_satellite_provider


SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [
            [21.10, 44.70],
            [21.105, 44.70],
            [21.105, 44.705],
            [21.10, 44.705],
            [21.10, 44.70],
        ]
    ],
}


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class SatelliteApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["SATELLITE_PROVIDER"] = "fake"
        reload_settings()
        reload_satellite_provider()
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def test_monitoring_requires_boundary_then_refresh(self) -> None:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json={
                "name": f"AT-sat-{uuid4().hex[:8]}",
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
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        parcel_id = created.json()["id"]
        try:
            empty = self.client.get(f"/api/v1/parcels/{parcel_id}/satellite", headers=self.headers)
            self.assertEqual(empty.status_code, 200, empty.text)
            self.assertEqual(empty.json()["status"], "boundary_required")

            patched = self.client.patch(
                f"/api/v1/parcels/{parcel_id}",
                headers=self.headers,
                json={"boundary": SQUARE},
            )
            self.assertEqual(patched.status_code, 200, patched.text)

            refresh = self.client.post(
                f"/api/v1/parcels/{parcel_id}/satellite/refresh",
                headers=self.headers,
            )
            self.assertEqual(refresh.status_code, 200, refresh.text)
            body = refresh.json()
            self.assertEqual(body["status"], "completed")
            self.assertFalse(body["skipped_duplicate"])

            again = self.client.post(
                f"/api/v1/parcels/{parcel_id}/satellite/refresh",
                headers=self.headers,
            )
            self.assertEqual(again.status_code, 200, again.text)
            self.assertTrue(again.json()["skipped_duplicate"])

            monitoring = self.client.get(f"/api/v1/parcels/{parcel_id}/satellite", headers=self.headers)
            self.assertEqual(monitoring.status_code, 200, monitoring.text)
            payload = monitoring.json()
            self.assertTrue(payload["available"])
            self.assertIsNotNone(payload["latest"])
            self.assertGreaterEqual(len(payload["latest"]["zones"]), 1)
            self.assertIn("ndvi", payload["index_formulas"])
            caps = payload["capabilities"]
            self.assertTrue(caps["has_boundary"])
            self.assertTrue(caps["has_aggregate_indices"])
            self.assertTrue(caps["has_zone_statistics"])
            self.assertTrue(caps["has_index_raster"])
            layers = payload["latest"].get("visualization_layers") or []
            self.assertGreaterEqual(len(layers), 1)
            viz = self.client.get(
                f"/api/v1/satellite/observations/{payload['latest']['id']}/visualizations/ndvi",
                headers=self.headers,
            )
            self.assertEqual(viz.status_code, 200, viz.text)
            self.assertIn("image/", viz.headers.get("content-type", ""))
        finally:
            self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)
