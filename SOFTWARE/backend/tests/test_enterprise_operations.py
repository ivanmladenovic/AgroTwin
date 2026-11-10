"""Members, temporary password, follow-ups and alert CSV."""

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
from app.models.enterprise import EnterpriseAuditEvent, EnterpriseMembership, EnterpriseParcelAssignment, EnterpriseSupplierLink
from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseRelationshipStatus,
    ParcelAlertSeverity,
    ParcelAlertStatus,
)
from app.models.intelligence import ParcelAlert
from app.models.user import User
from app.services.enterprise import ensure_organization


class EnterpriseOperationsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        cls.password = "EnterpriseOpsPass1!"
        suffix = uuid4().hex[:8]
        cls.email = f"ops-admin-{suffix}@agrotwin.rs"
        cls.viewer_email = f"ops-viewer-{suffix}@agrotwin.rs"
        cls.fresh_email = f"ops-fresh-{suffix}@agrotwin.rs"

        demo = cls.client.post(
            "/api/v1/auth/login",
            json={"email": "admin@agrotwin.rs", "password": "Mladenovic12345!"},
        )
        if demo.status_code != 200:
            raise AssertionError(demo.text)
        headers = {"Authorization": f"Bearer {demo.json()['access_token']}"}
        parcels = cls.client.get("/api/v1/parcels", headers=headers)
        assert parcels.status_code == 200, parcels.text
        payload = parcels.json()
        cls.parcel_id = payload[0]["id"]
        cls.farm_id = payload[0]["farm_id"]
        cls.other_parcel_id = payload[1]["id"] if len(payload) > 1 else None

        admin = User(
            email=cls.email,
            full_name="Ops Admin",
            hashed_password=hash_password(cls.password),
            is_active=True,
            is_superuser=False,
            must_change_password=False,
        )
        viewer = User(
            email=cls.viewer_email,
            full_name="Ops Viewer",
            hashed_password=hash_password(cls.password),
            is_active=True,
            is_superuser=False,
            must_change_password=False,
        )
        cls.db.add(admin)
        cls.db.add(viewer)
        cls.db.flush()
        org = ensure_organization(cls.db, name="Ops Org", slug=f"ops-{suffix}")
        cls.org_id = str(org.id)
        cls.admin_id = admin.id
        cls.db.add(
            EnterpriseMembership(
                organization_id=org.id,
                user_id=admin.id,
                role=EnterpriseMembershipRole.ENTERPRISE_ADMIN,
                status=EnterpriseMembershipStatus.ACTIVE,
            )
        )
        cls.db.add(
            EnterpriseMembership(
                organization_id=org.id,
                user_id=viewer.id,
                role=EnterpriseMembershipRole.ENTERPRISE_VIEWER,
                status=EnterpriseMembershipStatus.ACTIVE,
            )
        )
        cls.db.add(
            EnterpriseSupplierLink(
                organization_id=org.id,
                farm_id=cls.farm_id,
                status=EnterpriseRelationshipStatus.ACTIVE,
                assigned_by_id=admin.id,
            )
        )
        cls.db.add(
            EnterpriseParcelAssignment(
                organization_id=org.id,
                farm_id=cls.farm_id,
                parcel_id=cls.parcel_id,
                status=EnterpriseAssignmentStatus.ACTIVE,
                assigned_by_id=admin.id,
            )
        )
        cls.alert = ParcelAlert(
            parcel_id=cls.parcel_id,
            severity=ParcelAlertSeverity.WARNING,
            status=ParcelAlertStatus.OPEN,
            issue_key=f"ops-{suffix}",
            title="Ops alert",
            summary="=CMD()",
            observed_facts=[],
            possible_causes=[],
            recommended_actions=[],
            source_events=[],
            evidence={"observation_date": "2026-06-01"},
        )
        cls.db.add(cls.alert)
        cls.db.commit()
        cls.alert_id = str(cls.alert.id)
        cls.headers = cls._login(cls.email)
        cls.viewer_headers = cls._login(cls.viewer_email)

    @classmethod
    def _login(cls, email: str) -> dict[str, str]:
        response = cls.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": cls.password},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close()

    def test_new_member_must_change_password_before_data(self) -> None:
        created = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/memberships",
            headers=self.headers,
            json={
                "email": self.fresh_email,
                "full_name": "Novi clan",
                "role": "enterprise_analyst",
                "temporary_password": self.password,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": self.fresh_email, "password": self.password},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = {"Authorization": f"Bearer {login.json()['access_token']}"}
        me = self.client.get("/api/v1/enterprise/me", headers=token)
        self.assertEqual(me.status_code, 200, me.text)
        self.assertTrue(me.json()["must_change_password"])
        blocked = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/dashboard",
            headers=token,
        )
        self.assertEqual(blocked.status_code, 403, blocked.text)
        changed = self.client.post(
            "/api/v1/enterprise/change-password",
            headers=token,
            json={"current_password": self.password, "new_password": "NovaLozinka1!"},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        again = self.client.post(
            "/api/v1/auth/login",
            json={"email": self.fresh_email, "password": "NovaLozinka1!"},
        )
        self.assertEqual(again.status_code, 200, again.text)
        opened = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/dashboard",
            headers={"Authorization": f"Bearer {again.json()['access_token']}"},
        )
        self.assertEqual(opened.status_code, 200, opened.text)

    def test_existing_email_reuses_user_and_viewer_cannot_add_members(self) -> None:
        listed = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/memberships",
            headers=self.viewer_headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        denied = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/memberships",
            headers=self.viewer_headers,
            json={
                "email": f"blocked-{uuid4().hex[:6]}@agrotwin.rs",
                "full_name": "Ne sme",
                "role": "enterprise_viewer",
                "temporary_password": self.password,
            },
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        reused = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/memberships",
            headers=self.headers,
            json={
                "email": self.viewer_email,
                "full_name": "Ops Viewer",
                "role": "enterprise_viewer",
            },
        )
        self.assertEqual(reused.status_code, 201, reused.text)
        user = self.db.query(User).filter(User.email == self.viewer_email).one()
        self.assertFalse(user.must_change_password)

    def test_last_admin_cannot_deactivate_self(self) -> None:
        membership = (
            self.db.query(EnterpriseMembership)
            .filter(
                EnterpriseMembership.organization_id == self.org_id,
                EnterpriseMembership.user_id == self.admin_id,
            )
            .one()
        )
        response = self.client.patch(
            f"/api/v1/enterprise/organizations/{self.org_id}/memberships/{membership.id}",
            headers=self.headers,
            json={"status": "inactive"},
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_follow_up_permissions_and_parcel_scope(self) -> None:
        denied = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/follow-ups",
            headers=self.viewer_headers,
            json={"title": "Ne sme"},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        created = self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_id}/follow-ups",
            headers=self.headers,
            json={
                "title": "Proveri snimak",
                "parcel_id": self.parcel_id,
                "alert_id": self.alert_id,
                "due_on": "2020-01-01",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        task_id = created.json()["id"]
        overdue = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/follow-ups?due=overdue",
            headers=self.viewer_headers,
        )
        self.assertEqual(overdue.status_code, 200, overdue.text)
        self.assertTrue(any(item["id"] == task_id for item in overdue.json()))
        updated = self.client.patch(
            f"/api/v1/enterprise/organizations/{self.org_id}/follow-ups/{task_id}",
            headers=self.headers,
            json={"status": "completed"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["status"], "completed")
        if self.other_parcel_id and self.other_parcel_id != self.parcel_id:
            foreign = self.client.post(
                f"/api/v1/enterprise/organizations/{self.org_id}/follow-ups",
                headers=self.headers,
                json={"title": "Tuđa parcela", "parcel_id": self.other_parcel_id},
            )
            self.assertEqual(foreign.status_code, 403, foreign.text)

    def test_alert_csv_escapes_formula_and_audits(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/exports/intelligence-alerts.csv",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("alert_id,supplier,parcel", response.text)
        self.assertIn("'=CMD()", response.text)
        self.db.expire_all()
        audit = (
            self.db.query(EnterpriseAuditEvent)
            .filter(
                EnterpriseAuditEvent.organization_id == self.org_id,
                EnterpriseAuditEvent.action == "export_generated",
                EnterpriseAuditEvent.entity_type == "intelligence_alert_csv",
            )
            .all()
        )
        self.assertTrue(audit)
        self.assertNotIn("password", str(audit[-1].details).lower())

    def test_data_quality_counts_are_readable(self) -> None:
        response = self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_id}/data-quality?year=2026",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertGreaterEqual(body["assigned_parcels"], 1)
        self.assertGreaterEqual(body["open_alert"], 1)
        self.assertTrue(any("30%" in note for note in body["notes"]))
        denied = self.client.get(
            f"/api/v1/enterprise/organizations/{uuid4()}/data-quality",
            headers=self.headers,
        )
        self.assertIn(denied.status_code, {403, 404})
