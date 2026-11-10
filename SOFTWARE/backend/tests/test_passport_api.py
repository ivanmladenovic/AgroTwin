from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app
from app.passport.qr import generate_qr_png
from app.services.passport import _new_token


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class PassportApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        assert parcels.status_code == 200, parcels.text
        payload = parcels.json()
        assert payload, "Nema parcela"
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        cls.lot_ids: list[str] = []
        cls.harvest_ids: list[str] = []

    @classmethod
    def tearDownClass(cls) -> None:
        for harvest_id in cls.harvest_ids:
            cls.client.delete(
                f"/api/v1/parcels/{cls.parcel['id']}/harvests/{harvest_id}",
                headers=cls.headers,
            )

    def _create_harvest(self) -> dict:
        response = self.client.post(
            f"/api/v1/parcels/{self.parcel['id']}/harvests",
            headers=self.headers,
            json={
                "harvested_on": date.today().isoformat(),
                "scope_type": "parcel",
                "gross_quantity": "120.5",
                "loss_quantity": "5",
                "unit": "kg",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.harvest_ids.append(body["id"])
        return body

    def _create_lot(self, harvest_id: str, **overrides) -> dict:
        payload = {
            "harvest_id": harvest_id,
            "allow_indexing": False,
            "finalize": False,
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/harvest-lots", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.lot_ids.append(body["id"])
        return body

    def test_secure_token_generation(self) -> None:
        a = _new_token()
        b = _new_token()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 32)
        self.assertFalse(a.isdigit())

    def test_qr_png_generation(self) -> None:
        png = generate_qr_png("http://localhost:5174/passport/example-token")
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertGreater(len(png), 100)

    def test_lot_creation_and_unique_lot_number(self) -> None:
        harvest_a = self._create_harvest()
        harvest_b = self._create_harvest()
        lot_a = self._create_lot(harvest_a["id"])
        lot_b = self._create_lot(harvest_b["id"])

        self.assertTrue(lot_a["lot_number"].startswith(f"AT-{date.today().year}-"))
        self.assertNotEqual(lot_a["lot_number"], lot_b["lot_number"])
        self.assertNotEqual(lot_a["passport_token"], lot_b["passport_token"])
        self.assertNotIn(str(harvest_a["id"]), lot_a["public_url"])
        self.assertIn(lot_a["passport_token"], lot_a["public_url"])
        self.assertEqual(lot_a["crop"], "Lesnik")
        self.assertIsNotNone(lot_a["quantity"])
        self.assertEqual(Decimal(str(lot_a["quantity"])), Decimal("115.500"))

    def test_duplicate_lot_for_same_harvest_rejected(self) -> None:
        harvest = self._create_harvest()
        self._create_lot(harvest["id"])
        response = self.client.post(
            "/api/v1/harvest-lots",
            headers=self.headers,
            json={"harvest_id": harvest["id"]},
        )
        self.assertEqual(response.status_code, 409)

    def test_public_passport_no_auth_and_privacy(self) -> None:
        harvest = self._create_harvest()
        lot = self._create_lot(
            harvest["id"],
            visibility={
                "producer": True,
                "orchard": True,
                "location": True,
                "product": True,
                "quantity": False,
                "production_practices": True,
            },
        )
        public = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}")
        self.assertEqual(public.status_code, 200, public.text)
        body = public.json()
        self.assertEqual(body["lot_number"], lot["lot_number"])
        self.assertIsNotNone(body["producer"])
        self.assertIsNotNone(body["product"])
        self.assertIsNone(body["product"]["quantity"])
        self.assertNotIn("email", str(body).lower())
        self.assertNotIn(str(harvest["id"]), str(body))
        self.assertTrue(body["traceability"])
        self.assertFalse(body["allow_indexing"])
        self.assertEqual(public.headers.get("cache-control"), "no-store")
        self.assertIn("Tonda di Giffoni", body["product"]["varieties"])
        self.assertIn("Tonda Gentile Romana", body["product"]["varieties"])
        self.assertIn("Nocchione", body["product"]["varieties"])

        qr = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}/qr.png")
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr.headers["content-type"], "image/png")
        self.assertTrue(qr.content.startswith(b"\x89PNG"))

    def test_unauthorized_access_to_management(self) -> None:
        response = self.client.get("/api/v1/harvest-lots")
        self.assertEqual(response.status_code, 401)
        response = self.client.post("/api/v1/harvest-lots", json={"harvest_id": str(uuid4())})
        self.assertEqual(response.status_code, 401)

    def test_unknown_token_not_found(self) -> None:
        response = self.client.get("/api/v1/public/passports/not-a-real-token-xxxxxxxxxxxx")
        self.assertEqual(response.status_code, 404)

    def test_passport_snapshot_on_finalize(self) -> None:
        harvest = self._create_harvest()
        lot = self._create_lot(harvest["id"])
        finalized = self.client.post(
            f"/api/v1/harvest-lots/{lot['id']}/finalize",
            headers=self.headers,
        )
        self.assertEqual(finalized.status_code, 200, finalized.text)
        body = finalized.json()
        self.assertEqual(body["passport_status"], "finalized")
        self.assertEqual(body["snapshot_version"], 1)
        self.assertIsNotNone(body["finalized_at"])

        public = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}")
        self.assertEqual(public.status_code, 200)
        self.assertTrue(public.json()["finalized"])

        # Finalized lots cannot be edited.
        blocked = self.client.patch(
            f"/api/v1/harvest-lots/{lot['id']}",
            headers=self.headers,
            json={"crop": "Changed"},
        )
        self.assertEqual(blocked.status_code, 422)

    def test_revoked_passport(self) -> None:
        harvest = self._create_harvest()
        lot = self._create_lot(harvest["id"])
        revoked = self.client.post(
            f"/api/v1/harvest-lots/{lot['id']}/revoke",
            headers=self.headers,
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["passport_status"], "revoked")

        public = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}")
        self.assertEqual(public.status_code, 410)
        self.assertEqual(public.json().get("code"), "passport_revoked")
        self.assertEqual(public.headers.get("cache-control"), "no-store")

        qr = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}/qr.png")
        self.assertEqual(qr.status_code, 410)

        restored = self.client.post(
            f"/api/v1/harvest-lots/{lot['id']}/restore",
            headers=self.headers,
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["passport_status"], "published")
        self.assertIsNone(restored.json()["revoked_at"])
        self.assertEqual(restored.json()["passport_token"], lot["passport_token"])

        again = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}")
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["passport_status"], "published")

    def test_mobile_public_route_shape(self) -> None:
        harvest = self._create_harvest()
        lot = self._create_lot(harvest["id"], finalize=True)
        self.assertTrue(lot["public_url"].endswith(f"/passport/{lot['passport_token']}"))
        public = self.client.get(f"/api/v1/public/passports/{lot['passport_token']}")
        self.assertEqual(public.status_code, 200)
        body = public.json()
        # Compact fields suitable for mobile QR scan landing.
        self.assertIn("producer", body)
        self.assertIn("orchard", body)
        self.assertIn("product", body)
        self.assertIn("traceability", body)
        self.assertIn("metadata", body)
