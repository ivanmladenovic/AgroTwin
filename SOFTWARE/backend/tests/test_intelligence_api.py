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


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class IntelligenceApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["SATELLITE_PROVIDER"] = "fake"
        os.environ["AI_PROVIDER"] = "local"
        os.environ["AI_INTELLIGENCE_ENABLED"] = "true"
        os.environ["AI_ANALYSIS_MIN_INTERVAL_HOURS"] = "0"
        reload_settings()
        reload_satellite_provider()
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def test_manual_analyze_and_dashboard(self) -> None:
        created = self.client.post(
            "/api/v1/parcels",
            headers=self.headers,
            json={
                "name": f"AT-intel-{uuid4().hex[:8]}",
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
                "boundary": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [21.20, 44.80],
                            [21.205, 44.80],
                            [21.205, 44.805],
                            [21.20, 44.805],
                            [21.20, 44.80],
                        ]
                    ],
                },
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        parcel_id = created.json()["id"]
        try:
            # Seed a satellite observation so context is non-empty
            refresh = self.client.post(
                f"/api/v1/parcels/{parcel_id}/satellite/refresh",
                headers=self.headers,
            )
            self.assertEqual(refresh.status_code, 200, refresh.text)

            analyze = self.client.post(
                f"/api/v1/parcels/{parcel_id}/intelligence/analyze",
                headers=self.headers,
            )
            self.assertEqual(analyze.status_code, 200, analyze.text)
            body = analyze.json()
            self.assertTrue(body["ai_called"])
            self.assertEqual(body["status"], "completed")

            dash = self.client.get(
                f"/api/v1/parcels/{parcel_id}/intelligence",
                headers=self.headers,
            )
            self.assertEqual(dash.status_code, 200, dash.text)
            payload = dash.json()
            self.assertTrue(payload["available"])
            self.assertIsNotNone(payload["last_analysis"])
        finally:
            self.client.delete(f"/api/v1/parcels/{parcel_id}", headers=self.headers)
