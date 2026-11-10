from __future__ import annotations

from datetime import date, timedelta
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


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _money(value: str | int | float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


class WorkforceApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        parcels = cls.client.get("/api/v1/parcels", headers=cls.headers)
        assert parcels.status_code == 200, parcels.text
        payload = parcels.json()
        assert payload, "Nema parcela"
        cls.parcel = next((item for item in payload if item["name"] == "Kusiljevo"), payload[0])
        types = cls.client.get("/api/v1/work-task-types", headers=cls.headers)
        assert types.status_code == 200, types.text
        if not types.json():
            # Lifespan seed may have run before the workforce migration; ensure catalog exists.
            from app.db.session import SessionLocal
            from app.services.catalog import CatalogService

            db = SessionLocal()
            try:
                CatalogService(db).upsert_defaults()
                db.commit()
            finally:
                db.close()
            types = cls.client.get("/api/v1/work-task-types", headers=cls.headers)
            assert types.status_code == 200, types.text
        assert types.json(), "Nema tipova zadataka"
        cls.task_type = types.json()[0]
        cls.worker_ids: list[str] = []
        cls.task_ids: list[str] = []

    @classmethod
    def tearDownClass(cls) -> None:
        for task_id in cls.task_ids:
            cls.client.delete(f"/api/v1/work-tasks/{task_id}", headers=cls.headers)
        for worker_id in cls.worker_ids:
            cls.client.delete(f"/api/v1/workers/{worker_id}", headers=cls.headers)

    def _create_worker(self, **overrides) -> dict:
        payload = {
            "first_name": f"Petar{uuid4().hex[:4]}",
            "last_name": "Radnik",
            "hourly_rate": "12.50",
            "active": True,
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/workers", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.worker_ids.append(body["id"])
        return body

    def _create_task(self, worker_id: str, **overrides) -> dict:
        payload = {
            "worker_id": worker_id,
            "parcel_id": self.parcel["id"],
            "task_type_id": self.task_type["id"],
            "worked_on": date.today().isoformat(),
            "hours": "4",
            "status": "completed",
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/work-tasks", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.task_ids.append(body["id"])
        return body

    def test_requires_auth(self) -> None:
        response = self.client.get("/api/v1/workers")
        self.assertEqual(response.status_code, 401)
        response = self.client.post("/api/v1/work-tasks", json={})
        self.assertEqual(response.status_code, 401)

    def test_labor_cost_calculation(self) -> None:
        worker = self._create_worker(hourly_rate="15.00")
        task = self._create_task(worker["id"], hours="3.5")
        self.assertEqual(_money(task["hourly_rate_snapshot"]), Decimal("15.00"))
        self.assertEqual(_money(task["labor_cost"]), Decimal("52.50"))

    def test_rate_snapshot_not_affected_by_worker_rate_change(self) -> None:
        worker = self._create_worker(hourly_rate="10.00")
        task = self._create_task(worker["id"], hours="2")
        self.assertEqual(_money(task["hourly_rate_snapshot"]), Decimal("10.00"))
        self.assertEqual(_money(task["labor_cost"]), Decimal("20.00"))

        updated = self.client.patch(
            f"/api/v1/workers/{worker['id']}",
            headers=self.headers,
            json={"hourly_rate": "25.00"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(_money(updated.json()["hourly_rate"]), Decimal("25.00"))

        fetched = self.client.get(f"/api/v1/work-tasks/{task['id']}", headers=self.headers)
        self.assertEqual(fetched.status_code, 200, fetched.text)
        body = fetched.json()
        self.assertEqual(_money(body["hourly_rate_snapshot"]), Decimal("10.00"))
        self.assertEqual(_money(body["labor_cost"]), Decimal("20.00"))

    def test_parcel_cost_integration(self) -> None:
        worker = self._create_worker(hourly_rate="8.00")
        task = self._create_task(worker["id"], hours="5", description="Košenje reda 1")
        self.assertIsNotNone(task["cost_id"])

        costs = self.client.get(
            "/api/v1/costs",
            headers=self.headers,
            params={"parcel_id": self.parcel["id"]},
        )
        self.assertEqual(costs.status_code, 200, costs.text)
        match = next((item for item in costs.json() if item["id"] == task["cost_id"]), None)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match["source"], "work_task")
        self.assertEqual(match["source_id"], task["id"])
        self.assertEqual(match["cost_category"]["slug"], "labor")
        self.assertEqual(_money(match["amount"]), Decimal("40.00"))
        self.assertEqual(match["parcel_id"], self.parcel["id"])

    def test_filtering(self) -> None:
        worker_a = self._create_worker(first_name="Ana", last_name="A")
        worker_b = self._create_worker(first_name="Boro", last_name="B")
        day = date.today()
        task_a = self._create_task(worker_a["id"], worked_on=day.isoformat(), hours="1")
        task_b = self._create_task(
            worker_b["id"],
            worked_on=(day - timedelta(days=10)).isoformat(),
            hours="2",
        )

        by_worker = self.client.get(
            "/api/v1/work-tasks",
            headers=self.headers,
            params={"worker_id": worker_a["id"]},
        )
        self.assertEqual(by_worker.status_code, 200)
        ids = {item["id"] for item in by_worker.json()}
        self.assertIn(task_a["id"], ids)
        self.assertNotIn(task_b["id"], ids)

        by_date = self.client.get(
            "/api/v1/work-tasks",
            headers=self.headers,
            params={"date_from": day.isoformat(), "date_to": day.isoformat()},
        )
        self.assertEqual(by_date.status_code, 200)
        date_ids = {item["id"] for item in by_date.json()}
        self.assertIn(task_a["id"], date_ids)
        self.assertNotIn(task_b["id"], date_ids)

        by_parcel = self.client.get(
            "/api/v1/work-tasks",
            headers=self.headers,
            params={"parcel_id": self.parcel["id"]},
        )
        self.assertEqual(by_parcel.status_code, 200)
        parcel_ids = {item["id"] for item in by_parcel.json()}
        self.assertIn(task_a["id"], parcel_ids)
        self.assertIn(task_b["id"], parcel_ids)

        by_type = self.client.get(
            "/api/v1/work-tasks",
            headers=self.headers,
            params={"task_type_id": self.task_type["id"]},
        )
        self.assertEqual(by_type.status_code, 200)
        type_ids = {item["id"] for item in by_type.json()}
        self.assertIn(task_a["id"], type_ids)

    def test_edit_historical_task_updates_cost_keeps_snapshot_unless_rate_edited(self) -> None:
        worker = self._create_worker(hourly_rate="10.00")
        task = self._create_task(worker["id"], hours="2")
        self.assertEqual(_money(task["labor_cost"]), Decimal("20.00"))
        cost_id = task["cost_id"]

        # Changing hours recalculates labor_cost using existing snapshot.
        updated = self.client.patch(
            f"/api/v1/work-tasks/{task['id']}",
            headers=self.headers,
            json={"hours": "3"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        body = updated.json()
        self.assertEqual(_money(body["hourly_rate_snapshot"]), Decimal("10.00"))
        self.assertEqual(_money(body["labor_cost"]), Decimal("30.00"))
        self.assertEqual(body["cost_id"], cost_id)

        costs = self.client.get("/api/v1/costs", headers=self.headers, params={"parcel_id": self.parcel["id"]})
        match = next(item for item in costs.json() if item["id"] == cost_id)
        self.assertEqual(_money(match["amount"]), Decimal("30.00"))

        # Explicit hourly_rate edit updates snapshot for this task only.
        rate_edit = self.client.patch(
            f"/api/v1/work-tasks/{task['id']}",
            headers=self.headers,
            json={"hourly_rate": "12.00"},
        )
        self.assertEqual(rate_edit.status_code, 200, rate_edit.text)
        rate_body = rate_edit.json()
        self.assertEqual(_money(rate_body["hourly_rate_snapshot"]), Decimal("12.00"))
        self.assertEqual(_money(rate_body["labor_cost"]), Decimal("36.00"))

        # Cancelling removes linked cost.
        cancelled = self.client.patch(
            f"/api/v1/work-tasks/{task['id']}",
            headers=self.headers,
            json={"status": "cancelled"},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertIsNone(cancelled.json()["cost_id"])

    def test_dashboard_and_parcel_labor(self) -> None:
        worker = self._create_worker(hourly_rate="9.00")
        self._create_task(worker["id"], hours="4")
        dashboard = self.client.get(
            "/api/v1/workforce/dashboard",
            headers=self.headers,
            params={"parcel_id": self.parcel["id"]},
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        data = dashboard.json()
        self.assertGreaterEqual(_money(data["total_labor_cost"]), Decimal("36.00"))
        self.assertGreaterEqual(data["worker_count"], 1)
        self.assertTrue(data["by_worker"])
        self.assertTrue(data["by_task_type"])
        self.assertTrue(data["by_parcel"])

        labor = self.client.get(f"/api/v1/parcels/{self.parcel['id']}/labor", headers=self.headers)
        self.assertEqual(labor.status_code, 200, labor.text)
        summary = labor.json()
        self.assertGreaterEqual(_money(summary["total_labor_cost"]), Decimal("36.00"))
        self.assertTrue(summary["recent_tasks"])

    def test_planned_task_has_no_cost(self) -> None:
        worker = self._create_worker(hourly_rate="11.00")
        task = self._create_task(worker["id"], hours="2", status="planned")
        self.assertIsNone(task["cost_id"])
        self.assertEqual(_money(task["labor_cost"]), Decimal("22.00"))
