from pathlib import Path
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


def _tree_on_row(client: TestClient, headers: dict[str, str], parcel_id: str, row_id: str, position: int) -> dict:
    trees = client.get(
        f"/api/v1/parcels/{parcel_id}/trees",
        headers=headers,
        params={"row_id": row_id},
    ).json()
    return next(item for item in trees if item["position_in_row"] == position)


def verify_tree_health() -> None:
    client = TestClient(app)
    headers = _auth(client)

    parcels = client.get("/api/v1/parcels", headers=headers).json()
    north = next(parcel for parcel in parcels if parcel["name"] in {"Severna padina", "North Slope"})
    rows = client.get(f"/api/v1/parcels/{north['id']}/rows", headers=headers).json()
    row_14 = next(row for row in rows if row["row_number"] == 14)

    cases = client.get("/api/v1/disease-cases", headers=headers)
    assert cases.status_code == 200, cases.text
    records = cases.json()
    assert len(records) >= 4
    blight = next(item for item in records if "blight" in item["title"].lower())
    weevil = next(item for item in records if "weevil" in item["title"].lower())
    nutrient = next(item for item in records if "nutrient" in item["title"].lower())
    damage = next(item for item in records if "bark" in item["title"].lower())
    assert blight["status"] == "monitoring"
    assert weevil["severity"] == "high" and weevil["status"] == "open"
    assert nutrient["category"] == "nutrient_deficiency"
    assert damage["status"] == "resolved"
    assert blight["observation_count"] >= 3

    detail = client.get(f"/api/v1/disease-cases/{blight['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert len(payload["observations"]) >= 3
    assert len(payload["photos"]) >= 3
    photo = payload["photos"][0]
    assert photo["original_filename"]
    assert photo["url"].endswith("/file")
    assert photo["uploaded_at"]
    file_response = client.get(f"/api/v1{photo['url']}", headers=headers)
    assert file_response.status_code == 200, file_response.text
    assert file_response.content[:8] == b"\x89PNG\r\n\x1a\n"

    if not any("API test observation" in (item.get("notes") or "") for item in payload["observations"]):
        observation = client.post(
            f"/api/v1/disease-cases/{blight['id']}/observations",
            headers=headers,
            json={
                "observed_on": "2026-09-14",
                "symptoms": "Follow-up check during verification; still no confirmed diagnosis.",
                "notes": "API test observation.",
            },
        )
        assert observation.status_code == 201, observation.text

    refreshed = client.get(f"/api/v1/disease-cases/{blight['id']}", headers=headers).json()
    assert len(refreshed["observations"]) >= 4

    twin = client.get(f"/api/v1/parcels/{north['id']}/twin", headers=headers)
    assert twin.status_code == 200, twin.text
    trees = {item["id"]: item for item in twin.json()["trees"]}
    blight_tree = _tree_on_row(client, headers, north["id"], row_14["id"], 38)
    weevil_tree = _tree_on_row(client, headers, north["id"], row_14["id"], 1)
    nutrient_tree = _tree_on_row(client, headers, north["id"], row_14["id"], 10)
    damage_tree = _tree_on_row(client, headers, north["id"], row_14["id"], 20)

    assert trees[blight_tree["id"]]["health_status"] == "monitoring"
    assert trees[weevil_tree["id"]]["health_status"] == "issue"
    assert trees[weevil_tree["id"]]["has_severe_case"] is True
    assert trees[nutrient_tree["id"]]["health_status"] == "monitoring"
    assert trees[damage_tree["id"]]["health_status"] == "healthy"
    assert trees[damage_tree["id"]]["has_severe_case"] is False

    journal = client.get(
        f"/api/v1/parcels/{north['id']}/trees/{blight_tree['id']}/journal",
        headers=headers,
    )
    assert journal.status_code == 200, journal.text
    tree_journal = journal.json()
    assert tree_journal["tree"]["health_status"] == "monitoring"
    assert len(tree_journal["open_cases"]) >= 1
    assert len(tree_journal["observations"]) >= 3
    assert len(tree_journal["photos"]) >= 3
    assert any(event["kind"] == "observation" for event in tree_journal["timeline"])

    resolved = client.patch(
        f"/api/v1/disease-cases/{weevil['id']}",
        headers=headers,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200, resolved.text
    after = client.get(f"/api/v1/parcels/{north['id']}/twin", headers=headers).json()
    after_trees = {item["id"]: item for item in after["trees"]}
    assert after_trees[weevil_tree["id"]]["health_status"] == "healthy"
    assert after_trees[weevil_tree["id"]]["has_severe_case"] is False

    restored = client.patch(
        f"/api/v1/disease-cases/{weevil['id']}",
        headers=headers,
        json={"status": "open"},
    )
    assert restored.status_code == 200, restored.text
    final = client.get(f"/api/v1/parcels/{north['id']}/twin", headers=headers).json()
    final_trees = {item["id"]: item for item in final["trees"]}
    assert final_trees[weevil_tree["id"]]["health_status"] == "issue"
    assert final_trees[weevil_tree["id"]]["has_severe_case"] is True

    print("Tree health verification passed.")


if __name__ == "__main__":
    verify_tree_health()
