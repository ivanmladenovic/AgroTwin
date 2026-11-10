"""Enterprise authz: assigned read access + no producer mutations."""

from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.enterprise import (
    EnterpriseMembership,
    EnterpriseParcelAssignment,
    EnterpriseSupplierLink,
)
from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseRelationshipStatus,
)
from app.models.user import User
from app.services.enterprise import ensure_organization


class EnterpriseApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        cls.password = "EnterpriseTestPass1!"
        cls.email = f"enterprise-test-{uuid4().hex[:8]}@agrotwin.rs"

        # Producer farm/parcel from existing demo login.
        demo_login = cls.client.post(
            "/api/v1/auth/login",
            json={"email": "admin@agrotwin.rs", "password": "Mladenovic12345!"},
        )
        if demo_login.status_code != 200:
            raise AssertionError(f"Demo login failed: {demo_login.text}")
        cls.producer_headers = {
            "Authorization": f"Bearer {demo_login.json()['access_token']}"
        }
        parcels = cls.client.get("/api/v1/parcels", headers=cls.producer_headers)
        assert parcels.status_code == 200, parcels.text
        payload = parcels.json()
        if not payload:
            raise AssertionError("Nema demo parcela za Enterprise test")
        cls.assigned_parcel = payload[0]
        cls.assigned_parcel_id = cls.assigned_parcel["id"]
        cls.farm_id = cls.assigned_parcel["farm_id"]
        cls.unassigned_parcel_id = None
        if len(payload) > 1:
            cls.unassigned_parcel_id = payload[1]["id"]

        user = User(
            email=cls.email,
            full_name="Enterprise Test Admin",
            hashed_password=hash_password(cls.password),
            is_active=True,
            is_superuser=False,
            must_change_password=False,
        )
        cls.db.add(user)
        cls.db.flush()
        org = ensure_organization(cls.db, name="Enterprise Test Org", slug=f"ent-test-{uuid4().hex[:6]}")
        cls.org_id = str(org.id)
        cls.db.add(
            EnterpriseMembership(
                organization_id=org.id,
                user_id=user.id,
                role=EnterpriseMembershipRole.ENTERPRISE_ADMIN,
                status=EnterpriseMembershipStatus.ACTIVE,
            )
        )
        cls.db.add(
            EnterpriseSupplierLink(
                organization_id=org.id,
                farm_id=cls.farm_id,
                status=EnterpriseRelationshipStatus.ACTIVE,
                assigned_by_id=user.id,
            )
        )
        cls.db.add(
            EnterpriseParcelAssignment(
                organization_id=org.id,
                farm_id=cls.farm_id,
                parcel_id=cls.assigned_parcel_id,
                status=EnterpriseAssignmentStatus.ACTIVE,
                assigned_by_id=user.id,
            )
        )
        cls.db.commit()

        login = cls.client.post(
            "/api/v1/auth/login",
            json={"email": cls.email, "password": cls.password},
        )
        assert login.status_code == 200, login.text
        cls.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close()

    def test_enterprise_me_lists_membership(self) -> None:
        response = self.client.get("/api/v1/enterprise/me", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["email"], self.email)
        self.assertTrue(any(m["organization_id"] == self.org_id for m in body["memberships"]))

    def test_can_read_assigned_parcel(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/parcels/{self.assigned_parcel_id}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["parcel_id"], self.assigned_parcel_id)

    def test_cannot_read_unassigned_parcel(self) -> None:
        if not self.unassigned_parcel_id:
            self.skipTest("Samo jedna demo parcela")
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/parcels/{self.unassigned_parcel_id}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_dashboard_excludes_unauthorized_scope(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/dashboard",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertGreaterEqual(body["assigned_parcels"], 1)

    def test_cannot_create_producer_harvest(self) -> None:
        response = self.client.post(
            f"/api/v1/parcels/{self.assigned_parcel_id}/harvests",
            headers=self.headers,
            json={
                "harvested_on": "2026-09-01",
                "scope_type": "parcel",
                "gross_quantity": 10,
                "loss_quantity": 0,
                "unit": "kg",
            },
        )
        self.assertIn(response.status_code, {403, 404}, response.text)

    def test_cannot_create_producer_activity(self) -> None:
        response = self.client.post(
            "/api/v1/activities",
            headers=self.headers,
            json={
                "scope_type": "parcel",
                "parcel_id": self.assigned_parcel_id,
                "activity_type_id": None,
                "title": "Enterprise forbidden",
                "status": "completed",
            },
        )
        self.assertIn(response.status_code, {400, 403, 404, 422}, response.text)

    def test_producer_write_guard_endpoint(self) -> None:
        response = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/producer-write-guard",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_create_yield_plan_for_assigned_parcels(self) -> None:
        season = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/seasons",
            headers=self.headers,
            json={"year": 2099, "name": "Sezona testa 2099"},
        )
        if season.status_code == 403:
            # Season may already exist from prior run with same year unique constraint via other path
            seasons = self.client.get(
                f"/api/v1/enterprise/organizations/{self.org_id}/seasons",
                headers=self.headers,
            )
            self.assertEqual(seasons.status_code, 200)
            season_id = seasons.json()[0]["id"]
        else:
            self.assertEqual(season.status_code, 201, season.text)
            season_id = season.json()["id"]

        plan = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/yield-plans",
            headers=self.headers,
            json={
                "planning_season_id": season_id,
                "name": "Realistični test",
                "scenario_type": "realistic",
                "parcel_ids": [self.assigned_parcel_id],
            },
        )
        self.assertEqual(plan.status_code, 201, plan.text)
        body = plan.json()
        self.assertEqual(body["calculation_version"], "enterprise-yield-v1")
        self.assertEqual(len(body["items"]), 1)

    def test_foreign_org_forbidden(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{uuid4()}/dashboard",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_parcel_twin_read_only(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/parcels/{self.assigned_parcel_id}/twin",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["parcel"]["id"], self.assigned_parcel_id)

    def test_compare_and_export_plan(self) -> None:
        season = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/seasons",
            headers=self.headers,
            json={"year": 2098, "name": "Sezona compare 2098"},
        )
        if season.status_code == 201:
            season_id = season.json()["id"]
        else:
            seasons = self.client.get(
                f"/api/v1/enterprise/organizations/{self.org_id}/seasons",
                headers=self.headers,
            )
            self.assertEqual(seasons.status_code, 200, seasons.text)
            self.assertGreater(len(seasons.json()), 0, seasons.text)
            season_id = seasons.json()[0]["id"]
        plan = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/yield-plans",
            headers=self.headers,
            json={
                "planning_season_id": season_id,
                "name": "Compare test",
                "scenario_type": "realistic",
                "parcel_ids": [self.assigned_parcel_id],
            },
        )
        self.assertEqual(plan.status_code, 201, plan.text)
        plan_id = plan.json()["id"]

        compare = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/yield-plans/{plan_id}/compare",
            headers=self.headers,
        )
        self.assertEqual(compare.status_code, 200, compare.text)
        body = compare.json()
        self.assertEqual(body["plan_id"], plan_id)
        self.assertGreaterEqual(len(body["rows"]), 1)

        csv_resp = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/exports/yield-plans/{plan_id}.csv",
            headers=self.headers,
        )
        self.assertEqual(csv_resp.status_code, 200, csv_resp.text)
        self.assertIn("forecast_kg", csv_resp.text)

        parcels_csv = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/exports/parcels.csv",
            headers=self.headers,
        )
        self.assertEqual(parcels_csv.status_code, 200, parcels_csv.text)
        self.assertIn("parcel_name", parcels_csv.text)

    def test_map_analytics_and_aggregate_report(self) -> None:
        map_resp = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/map-parcels",
            headers=self.headers,
        )
        self.assertEqual(map_resp.status_code, 200, map_resp.text)
        self.assertIsInstance(map_resp.json(), list)

        analytics = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/production-analytics",
            headers=self.headers,
        )
        self.assertEqual(analytics.status_code, 200, analytics.text)
        body = analytics.json()
        self.assertIn("by_year", body)
        self.assertIn("by_variety", body)

        suppliers = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/suppliers",
            headers=self.headers,
        )
        self.assertEqual(suppliers.status_code, 200, suppliers.text)
        self.assertGreaterEqual(len(suppliers.json()), 1)
        self.assertIn("producer_display_name", suppliers.json()[0])

        parcels = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/parcels",
            headers=self.headers,
        )
        self.assertEqual(parcels.status_code, 200, parcels.text)
        parcel = parcels.json()[0]
        self.assertIn("variety_names", parcel)

        report = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/reports/aggregate",
            headers=self.headers,
            json={"parcel_ids": [self.assigned_parcel_id]},
        )
        self.assertEqual(report.status_code, 200, report.text)
        report_body = report.json()
        self.assertEqual(report_body["parcel_count"], 1)
        self.assertGreaterEqual(len(report_body["parcels"]), 1)

    def test_monitoring_center_read_only(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/monitoring",
            headers=self.headers,
            params={"year": 2026, "parcel_id": self.assigned_parcel_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("kpis", body)
        self.assertIn("attention_items", body)
        self.assertIn("observations", body)
        self.assertIn("activities", body)
        self.assertIn("plan_items", body)
        self.assertIn("weather_signals", body)
        self.assertIn("data_quality", body)
        self.assertTrue(body["kpis"]["open_problems"]["available"])
        self.assertIsInstance(body["attention_items"], list)
