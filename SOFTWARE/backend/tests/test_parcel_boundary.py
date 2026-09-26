from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.geojson import InvalidParcelGeometry, validate_boundary_geojson
from app.core.varieties import DEFAULT_VARIETIES
from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app


SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [
            [21.10, 44.25],
            [21.12, 44.25],
            [21.12, 44.27],
            [21.10, 44.27],
            [21.10, 44.25],
        ]
    ],
}


class ParcelBoundaryTests(TestCase):
    def test_valid_polygon(self) -> None:
        geom = validate_boundary_geojson(SQUARE)
        self.assertEqual(geom["type"], "Polygon")

    def test_rejects_point(self) -> None:
        with self.assertRaises(InvalidParcelGeometry):
            validate_boundary_geojson({"type": "Point", "coordinates": [21.1, 44.2]})

    def test_rejects_open_ring(self) -> None:
        with self.assertRaises(InvalidParcelGeometry):
            validate_boundary_geojson(
                {"type": "Polygon", "coordinates": [[[21.1, 44.2], [21.2, 44.2], [21.2, 44.3]]]}
            )


class ParcelBoundaryApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        response = cls.client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert response.status_code == 200, response.text
        cls.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _create_parcel(self) -> dict[str, Any]:
        payload = {
            "name": f"AT-bound-{uuid4().hex[:8]}",
            "area_hectares": 0.5,
            "row_count": 1,
            "trees_per_row": 2,
            "row_spacing_m": 5,
            "tree_spacing_m": 3.5,
            "planting_year": 2024,
            "starting_tree_number": 1,
            "varieties": DEFAULT_VARIETIES,
            "row_plan": [{"row_number": 1, "variety": DEFAULT_VARIETIES[0]["name"], "missing_positions": []}],
        }
        created = self.client.post("/api/v1/parcels", headers=self.headers, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def test_invalid_boundary_rejected(self) -> None:
        parcel = self._create_parcel()
        try:
            response = self.client.patch(
                f"/api/v1/parcels/{parcel['id']}",
                headers=self.headers,
                json={"boundary": {"type": "Point", "coordinates": [21.1, 44.2]}},
            )
            self.assertEqual(response.status_code, 422)
        finally:
            self.client.delete(f"/api/v1/parcels/{parcel['id']}", headers=self.headers)
