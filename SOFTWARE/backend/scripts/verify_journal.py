from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def verify_journal_and_costs() -> None:
    client = TestClient(app)
    headers = _auth(client)

    types = client.get("/api/v1/activity-types", headers=headers)
    assert types.status_code == 200, types.text
    type_map = {item["slug"]: item for item in types.json()}
    assert "spraying" in type_map and "inspection" in type_map

    categories = client.get("/api/v1/cost-categories", headers=headers)
    assert categories.status_code == 200, categories.text
    category_map = {item["slug"]: item for item in categories.json()}
    assert "labor" in category_map and "plant_protection" in category_map
    assert "fertilizers" in category_map

    parcels = client.get("/api/v1/parcels", headers=headers).json()
    north = next(parcel for parcel in parcels if parcel["name"] in {"Severna padina", "North Slope"})
    rows = client.get(f"/api/v1/parcels/{north['id']}/rows", headers=headers).json()
    row_14 = next(row for row in rows if row["row_number"] == 14)
    trees = client.get(
        f"/api/v1/parcels/{north['id']}/trees",
        headers=headers,
        params={"row_id": row_14["id"]},
    ).json()
    tree = next(item for item in trees if item["position_in_row"] == 38)
    assert tree["public_id"].startswith("R14-T")

    activities = client.get("/api/v1/activities", headers=headers).json()
    assert len(activities) >= 5
    spraying = next(item for item in activities if item["activity_type"]["slug"] == "spraying")
    assert spraying["scope_type"] == "parcel"
    assert Decimal(str(spraying["total_cost"])) == Decimal("230.00")
    assert len(spraying["costs"]) == 3

    fertilization = next(item for item in activities if item["activity_type"]["slug"] == "fertilization")
    assert fertilization["scope_type"] == "row"
    assert fertilization["row_number"] == 14
    assert Decimal(str(fertilization["total_cost"])) == Decimal("35.00")

    inspection = next(item for item in activities if item["activity_type"]["slug"] == "inspection")
    assert inspection["scope_type"] == "tree"
    assert Decimal(str(inspection["total_cost"])) == Decimal("0")

    journal = client.get(
        f"/api/v1/parcels/{north['id']}/trees/{tree['id']}/journal",
        headers=headers,
    )
    assert journal.status_code == 200, journal.text
    payload = journal.json()
    assert Decimal(str(payload["direct_cost_total"])) == Decimal("40.00")
    assert payload["orchard_cost_total"]
    assert any(event["title"] == "Pregled" for event in payload["timeline"])

    created = client.post(
        "/api/v1/activities",
        headers=headers,
        json={
            "activity_type_id": type_map["maintenance"]["id"],
            "performed_on": "2026-09-14",
            "scope_type": "parcel",
            "parcel_id": north["id"],
            "description": "Verify parcel-level activity",
        },
    )
    assert created.status_code == 201, created.text
    activity_id = created.json()["id"]
    cost = client.post(
        f"/api/v1/activities/{activity_id}/costs",
        headers=headers,
        json={
            "description": "Contractor",
            "cost_category_id": category_map["labor"]["id"],
            "amount": "15.50",
            "currency": "EUR",
        },
    )
    assert cost.status_code == 201, cost.text
    extra = client.post(
        f"/api/v1/activities/{activity_id}/costs",
        headers=headers,
        json={
            "description": "Parts",
            "cost_category_id": category_map["maintenance"]["id"],
            "amount": "4.50",
            "currency": "EUR",
        },
    )
    assert extra.status_code == 201, extra.text
    detail = client.get(f"/api/v1/activities/{activity_id}", headers=headers).json()
    assert Decimal(str(detail["total_cost"])) == Decimal("20.00")
    assert len(detail["costs"]) == 2

    summary = client.get("/api/v1/costs/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert Decimal(str(body["total_costs"])) >= Decimal("337.00")
    assert body["cost_per_tree"] is not None
    assert body["cost_per_hectare"] is not None
    assert body["by_category"]
    assert body["by_activity_type"]

    csv_activities = client.get("/api/v1/activities/export.csv", headers=headers)
    assert csv_activities.status_code == 200
    assert "activity_type" in csv_activities.text
    assert "Prskanje" in csv_activities.text

    csv_costs = client.get("/api/v1/costs/export.csv", headers=headers)
    assert csv_costs.status_code == 200
    assert "Sredstvo za zaštitu bilja" in csv_costs.text or "Pesticide" in csv_costs.text
    assert "Rad" in csv_costs.text or "Labor" in csv_costs.text

    print("Phase 2/3 verified: parcel/row/tree activities, multi-cost totals, summaries and CSV export.")


if __name__ == "__main__":
    verify_journal_and_costs()
