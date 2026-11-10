from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest import TestCase
import sys
import zipfile
import io

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app
from app.compliance.pdf import render_report_pdf
from app.compliance.csv_export import render_report_csv
from app.schemas.compliance import ComplianceReportMeta, ComplianceReportResult
from app.models.enums import ComplianceReportType
from datetime import datetime, timezone


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class ComplianceApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        assert parcels.status_code == 200, parcels.text
        payload = parcels.json()
        assert payload
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        year = date.today().year
        cls.date_from = f"{year}-01-01"
        cls.date_to = f"{year}-12-31"

    def test_requires_auth(self) -> None:
        response = self.client.get("/api/v1/compliance/definitions")
        self.assertEqual(response.status_code, 401)
        response = self.client.get("/api/v1/compliance/reports/plant_protection")
        self.assertEqual(response.status_code, 401)

    def test_definitions_seeded(self) -> None:
        response = self.client.get("/api/v1/compliance/definitions", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        types = {item["type"] for item in response.json()}
        self.assertIn("plant_protection", types)
        self.assertIn("harvest_traceability", types)
        self.assertIn("farm_activity", types)
        self.assertIn("fertilization_inputs", types)

    def test_plant_protection_filters_and_empty(self) -> None:
        response = self.client.get(
            "/api/v1/compliance/reports/plant_protection",
            headers=self.headers,
            params={
                "date_from": self.date_from,
                "date_to": self.date_to,
                "parcel_id": self.parcel["id"],
                "product": "___no_such_product___",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["meta"]["record_count"], 0)
        self.assertEqual(body["rows"], [])
        self.assertIn("ne sertifikuje", body["meta"]["disclaimer"].lower())
        self.assertIn("globalg.a.p.", body["meta"]["disclaimer"].lower())

    def test_parcel_filter_on_farm_activity(self) -> None:
        all_parcels = self.client.get(
            "/api/v1/compliance/reports/farm_activity",
            headers=self.headers,
            params={"date_from": self.date_from, "date_to": self.date_to},
        )
        self.assertEqual(all_parcels.status_code, 200, all_parcels.text)
        filtered = self.client.get(
            "/api/v1/compliance/reports/farm_activity",
            headers=self.headers,
            params={
                "date_from": self.date_from,
                "date_to": self.date_to,
                "parcel_id": self.parcel["id"],
            },
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        for row in filtered.json()["rows"]:
            if row.get("Parcela"):
                self.assertEqual(row["Parcela"], self.parcel["name"])

    def test_date_range_filter(self) -> None:
        response = self.client.get(
            "/api/v1/compliance/reports/fertilization_inputs",
            headers=self.headers,
            params={"date_from": "1990-01-01", "date_to": "1990-01-02"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["meta"]["record_count"], 0)

    def test_harvest_traceability_shape(self) -> None:
        response = self.client.get(
            "/api/v1/compliance/reports/harvest_traceability",
            headers=self.headers,
            params={"date_from": self.date_from, "date_to": self.date_to},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("Broj lota", body["columns"])
        self.assertIn("Lanac sledljivosti", body["columns"])

    def test_csv_export(self) -> None:
        response = self.client.get(
            "/api/v1/compliance/reports/parcel_register/export.csv",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("Parcela", response.text)

    def test_pdf_generation(self) -> None:
        response = self.client.get(
            "/api/v1/compliance/reports/farm_profile/export.pdf",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_helper_empty_report(self) -> None:
        from uuid import UUID

        farms = self.client.get("/api/v1/farms", headers=self.headers)
        farm_id = UUID(farms.json()[0]["id"])
        result = ComplianceReportResult(
            meta=ComplianceReportMeta(
                report_type=ComplianceReportType.FARM_ACTIVITY,
                title="06 Farm Activity Report",
                farm_name="Test",
                farm_id=farm_id,
                generated_at=datetime.now(timezone.utc),
                filters={},
                record_count=0,
                disclaimer="AgroTwin Compliance Report. Prepared from records stored in AgroTwin.",
            ),
            columns=["date", "parcel", "activity"],
            rows=[],
            issues=[],
        )
        pdf = render_report_pdf(result)
        self.assertTrue(pdf.startswith(b"%PDF"))
        csv_text = render_report_csv(result)
        self.assertIn("Nema zapisa", csv_text)

    def test_audit_log_on_generate(self) -> None:
        before = self.client.get("/api/v1/compliance/runs", headers=self.headers)
        self.assertEqual(before.status_code, 200)
        count_before = len(before.json())
        # JSON preview must not create history noise.
        preview = self.client.get(
            "/api/v1/compliance/reports/farm_profile",
            headers=self.headers,
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        mid = self.client.get("/api/v1/compliance/runs", headers=self.headers)
        self.assertEqual(mid.status_code, 200)
        self.assertEqual(len(mid.json()), count_before)

        generated = self.client.get(
            "/api/v1/compliance/reports/farm_profile/export.pdf",
            headers=self.headers,
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        after = self.client.get("/api/v1/compliance/runs", headers=self.headers)
        self.assertEqual(after.status_code, 200)
        self.assertGreaterEqual(len(after.json()), count_before + 1)
        latest = after.json()[0]
        self.assertEqual(latest["report_type"], "farm_profile")
        self.assertEqual(latest["format"], "pdf")
        self.assertIsNotNone(latest["generated_by_id"])
        self.assertIn("filters", latest)

    def test_compliance_package_zip(self) -> None:
        response = self.client.post(
            "/api/v1/compliance/package",
            headers=self.headers,
            json={
                "date_from": self.date_from,
                "date_to": self.date_to,
                "parcel_ids": [self.parcel["id"]],
                "report_types": ["farm_profile", "parcel_register", "plant_protection"],
                "as_zip": True,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            self.assertIn("farm_profile.pdf", names)
            self.assertNotIn("farm_profile.csv", names)
            self.assertFalse(any(name.endswith(".csv") for name in names))
            self.assertIn("plant_protection.pdf", names)
            self.assertIn("README.txt", names)
            readme = archive.read("README.txt").decode("utf-8")
            self.assertIn("GLOBALG.A.P.", readme)
            self.assertIn("Generisano kroz AgroTwin", readme)
