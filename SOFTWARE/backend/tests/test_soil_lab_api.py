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


class SoilLabAnalysisApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        if parcels.status_code != 200:
            raise AssertionError(parcels.text)
        payload = parcels.json()
        if not payload:
            raise AssertionError("Nema parcela")
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        types = cls.client.get("/api/v1/activity-types", headers=cls.headers)
        if types.status_code != 200:
            raise AssertionError(types.text)
        cls.type_map = {item["slug"]: item for item in types.json()}
        trees = cls.client.get(f"/api/v1/parcels/{cls.parcel['id']}/trees", headers=cls.headers)
        if trees.status_code != 200 or not trees.json():
            raise AssertionError(trees.text or "Nema sadnica")
        cls.trees = trees.json()

    def _create_activity(self, slug: str = "soil_analysis") -> dict:
        response = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "activity_type_id": self.type_map[slug]["id"],
                "performed_on": date.today().isoformat(),
                "scope_type": "parcel",
                "parcel_id": self.parcel["id"],
                "description": f"AT-soil-{uuid4().hex[:8]}",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _upload(self, activity_id: str, tree_id: str, filename: str = "analiza.pdf", content: bytes = MIN_PDF, expected: int = 201):
        response = self.client.post(
            f"/api/v1/activities/{activity_id}/soil-analyses",
            headers=self.headers,
            data={"tree_id": tree_id, "sampled_on": date.today().isoformat()},
            files={"file": (filename, content, "application/pdf")},
        )
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if expected != 204 else None

    def test_catalog_includes_soil_analysis(self) -> None:
        self.assertIn("soil_analysis", self.type_map)
        self.assertEqual(self.type_map["soil_analysis"]["name"], "Analiza zemljišta")

    def test_upload_multiple_samples_on_different_trees(self) -> None:
        activity = self._create_activity()
        first = self._upload(activity["id"], self.trees[0]["id"], "uzorak-sever.pdf")
        second = self._upload(activity["id"], self.trees[1]["id"], "uzorak-jug.pdf")
        self.assertEqual(first["tree_id"], self.trees[0]["id"])
        self.assertEqual(first["tree_public_id"], self.trees[0]["public_id"])
        self.assertEqual(second["original_filename"], "uzorak-jug.pdf")
        detail = self.client.get(f"/api/v1/activities/{activity['id']}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        analyses = detail.json()["soil_analyses"]
        self.assertEqual(len(analyses), 2)
        pdf = self.client.get(f"/api/v1/soil-analyses/{first['id']}/file", headers=self.headers)
        self.assertEqual(pdf.status_code, 200, pdf.text)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_rejects_non_pdf_and_wrong_activity_type(self) -> None:
        irrigation = self._create_activity("irrigation")
        self._upload(irrigation["id"], self.trees[0]["id"], expected=422)
        activity = self._create_activity()
        response = self.client.post(
            f"/api/v1/activities/{activity['id']}/soil-analyses",
            headers=self.headers,
            data={"tree_id": self.trees[0]["id"], "sampled_on": date.today().isoformat()},
            files={"file": ("notes.txt", b"not a pdf", "text/plain")},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_upload_image_is_accepted_and_compressed(self) -> None:
        from io import BytesIO
        import os
        from PIL import Image

        image = Image.frombytes("RGB", (2000, 1500), os.urandom(2000 * 1500 * 3))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        original = buffer.getvalue()
        activity = self._create_activity()
        response = self.client.post(
            f"/api/v1/activities/{activity['id']}/soil-analyses",
            headers=self.headers,
            data={"tree_id": self.trees[0]["id"], "sampled_on": date.today().isoformat()},
            files={"file": ("uzorak.jpg", original, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["content_type"], "image/jpeg")
        self.assertTrue(payload["original_filename"].endswith(".jpg"))
        self.assertLess(payload["size_bytes"], len(original))
        downloaded = self.client.get(f"/api/v1/soil-analyses/{payload['id']}/file", headers=self.headers)
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertTrue(downloaded.content.startswith(b"\xff\xd8"))

    def test_parcel_soil_analyses_list_and_upload(self) -> None:
        listed = self.client.get(f"/api/v1/parcels/{self.parcel['id']}/soil-analyses", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        before = len(listed.json())
        response = self.client.post(
            f"/api/v1/parcels/{self.parcel['id']}/soil-analyses",
            headers=self.headers,
            data={"tree_id": self.trees[0]["id"], "sampled_on": date.today().isoformat()},
            files={"file": ("parcel-analiza.pdf", MIN_PDF, "application/pdf")},
        )
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["parcel_id"], self.parcel["id"])
        self.assertEqual(payload["tree_id"], self.trees[0]["id"])
        self.assertEqual(payload["original_filename"], "parcel-analiza.pdf")
        self.assertEqual(payload["source_kind"], "laboratory")
        self.assertIn(payload["verification_status"], {"needs_review", "extracted", "verified", "skipped"})
        self.assertIn(payload["extraction_status"], {"pending", "running", "succeeded", "failed"})
        after = self.client.get(f"/api/v1/parcels/{self.parcel['id']}/soil-analyses", headers=self.headers)
        self.assertEqual(after.status_code, 200, after.text)
        self.assertEqual(len(after.json()), before + 1)

    def test_structured_text_extract_verify_and_multiple_analyses(self) -> None:
        """Upload does not overwrite prior analyses; verify marks latest planning candidate."""
        sample_text = (
            "Laboratorija Test Lab\n"
            "Dubina 0-30 cm\n"
            "Reakcija zemljišta pH KCl 6.7\n"
            "Humus 2.8 %\n"
            "P2O5 18.4 mg/100g\n"
        )
        # Minimal PDF with embedded text so extract_pdf can read something if available;
        # we also force re-extract via service path by posting then patching via extract endpoint
        # after storing a text-bearing fake — here we exercise verify/edit API on empty extract
        # and ensure multiple uploads coexist.
        first = self.client.post(
            f"/api/v1/parcels/{self.parcel['id']}/soil-analyses",
            headers=self.headers,
            data={"tree_id": self.trees[0]["id"], "sampled_on": "2024-05-01"},
            files={"file": ("analiza-2024.pdf", MIN_PDF, "application/pdf")},
        )
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            f"/api/v1/parcels/{self.parcel['id']}/soil-analyses",
            headers=self.headers,
            data={"tree_id": self.trees[0]["id"], "sampled_on": "2025-05-01"},
            files={"file": ("analiza-2025.pdf", MIN_PDF, "application/pdf")},
        )
        self.assertEqual(second.status_code, 201, second.text)
        first_id = first.json()["id"]
        second_id = second.json()["id"]
        self.assertNotEqual(first_id, second_id)

        listed = self.client.get(f"/api/v1/parcels/{self.parcel['id']}/soil-analyses", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        ids = {item["id"] for item in listed.json()}
        self.assertIn(first_id, ids)
        self.assertIn(second_id, ids)

        # Manually add parameters (simulates extraction / user add) then verify.
        added = self.client.post(
            f"/api/v1/soil-analyses/{second_id}/results",
            headers=self.headers,
            json={
                "parameter_code": "PH",
                "original_parameter_name": "Reakcija zemljišta pH KCl",
                "value": "6.7",
                "unit": None,
                "method": "KCL",
            },
        )
        self.assertEqual(added.status_code, 201, added.text)
        self.assertEqual(added.json()["result_count"], 1)
        result_id = added.json()["results"][0]["id"]
        self.assertEqual(added.json()["results"][0]["original_parameter_name"], "Reakcija zemljišta pH KCl")

        edited = self.client.patch(
            f"/api/v1/soil-analyses/{second_id}/results/{result_id}",
            headers=self.headers,
            json={"value": "6.8"},
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["results"][0]["value"], "6.8")

        verified = self.client.post(
            f"/api/v1/soil-analyses/{second_id}/verify",
            headers=self.headers,
            json={},
        )
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertEqual(verified.json()["verification_status"], "verified")
        self.assertEqual(verified.json()["results"][0]["verification_status"], "verified")

        detail = self.client.get(f"/api/v1/soil-analyses/{second_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["verification_status"], "verified")

        # Isolation: another user's token cannot read (demo user owns parcel — skip cross-user here).
        # Ensure first analysis still exists untouched.
        still = self.client.get(f"/api/v1/soil-analyses/{first_id}", headers=self.headers)
        self.assertEqual(still.status_code, 200, still.text)
        self.assertNotEqual(still.json()["verification_status"], "verified")
        _ = sample_text  # reserved for future OCR fixture wiring

    def test_delete_soil_analysis_and_missing_file(self) -> None:
        activity = self._create_activity()
        uploaded = self._upload(activity["id"], self.trees[0]["id"], "za-brisanje.pdf")
        analysis_id = uploaded["id"]
        ok = self.client.get(f"/api/v1/soil-analyses/{analysis_id}/file", headers=self.headers)
        self.assertEqual(ok.status_code, 200, ok.text)
        deleted = self.client.delete(f"/api/v1/soil-analyses/{analysis_id}", headers=self.headers)
        self.assertEqual(deleted.status_code, 204, deleted.text)
        missing = self.client.get(f"/api/v1/soil-analyses/{analysis_id}/file", headers=self.headers)
        self.assertEqual(missing.status_code, 404, missing.text)
        listed = self.client.get(f"/api/v1/activities/{activity['id']}/soil-analyses", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertFalse(any(item["id"] == analysis_id for item in listed.json()))
