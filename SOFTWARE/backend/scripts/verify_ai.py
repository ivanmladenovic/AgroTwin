from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.knowledge.pdf import build_text_pdf
from app.main import app


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def verify_knowledge_and_ai() -> None:
    client = TestClient(app)
    headers = _auth(client)

    status = client.get("/api/v1/ai/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["provider"] in {"local", "openai_compatible"}

    documents = client.get("/api/v1/knowledge/documents", headers=headers)
    assert documents.status_code == 200, documents.text
    for item in documents.json():
        if item["title"] == "Retrieval probe":
            client.delete(f"/api/v1/knowledge/documents/{item['id']}", headers=headers)
    documents = client.get("/api/v1/knowledge/documents", headers=headers)
    assert documents.status_code == 200, documents.text
    assert len(documents.json()) >= 3
    assert all(item["status"] == "ready" for item in documents.json())
    assert all(item["chunk_count"] >= 1 for item in documents.json())

    extra = build_text_pdf(
        "Short retrieval probe",
        [("Probe heading", "This paragraph mentions phytophthora after waterlogging in hazelnut orchards.")],
    )
    uploaded = client.post(
        "/api/v1/knowledge/documents",
        headers=headers,
        files={"file": ("probe.pdf", extra, "application/pdf")},
        data={"title": "Retrieval probe", "category": "disease_guide"},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["chunk_count"] >= 1
    probe_id = uploaded.json()["id"]

    search = None
    hits = []
    for query in ("posle nekoliko kišnih dana", "after several days of rain"):
        search = client.get("/api/v1/knowledge/search", headers=headers, params={"q": query})
        assert search.status_code == 200, search.text
        hits = search.json()["hits"]
        if hits:
            break
    assert hits, search.text if search is not None else "no search"
    assert any(
        "kiš" in hit["content"].lower()
        or "kis" in hit["content"].lower()
        or "rain" in hit["content"].lower()
        or "kiš" in hit["document_title"].lower()
        or "rain" in hit["document_title"].lower()
        for hit in hits
    )

    created = client.post("/api/v1/ai/conversations", headers=headers, json={"title": "Verification"})
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    rain = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Šta da proverim posle nekoliko kišnih dana?"},
    )
    assert rain.status_code == 200, rain.text
    rain_payload = rain.json()
    assistant = rain_payload["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["sources"]
    content_l = assistant["content"].lower()
    assert any(word in content_l for word in ("dijagnoz", "diagnos", "opažanj", "observation", "kiš", "rain"))

    issues = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Koja stabla trenutno imaju nerešene probleme?"},
    )
    assert issues.status_code == 200, issues.text
    issues_text = issues.json()["messages"][-1]["content"].lower()
    assert any(
        word in issues_text
        for word in ("žižak", "zizak", "weevil", "r14-t0950", "nerešen", "unresolved", "open", "sumnja")
    )
    assert issues.json()["messages"][-1]["structured_refs"]

    spraying = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Kada je Red 14 poslednji put prskan?"},
    )
    assert spraying.status_code == 200, spraying.text
    spray_text = spraying.json()["messages"][-1]["content"].lower()
    assert "prskanj" in spray_text or "spray" in spray_text
    assert "2026-09-15" in spray_text or "15" in spray_text

    activities = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Koje aktivnosti su rađene na ovoj parceli ovog meseca?"},
    )
    assert activities.status_code == 200, activities.text
    activity_text = activities.json()["messages"][-1]["content"].lower()
    assert any(word in activity_text for word in ("prskanj", "spray", "navodnjav", "irrigat", "đubren", "djubren", "fertil"))

    cases = client.get("/api/v1/disease-cases", headers=headers).json()
    blight = next(item for item in cases if any(word in item["title"].lower() for word in ("blight", "rakovina")))
    detail = client.get(f"/api/v1/disease-cases/{blight['id']}", headers=headers).json()
    photo_id = detail["photos"][0]["id"] if detail["photos"] else None
    analysis = client.post(
        f"/api/v1/ai/disease-cases/{blight['id']}/analyses",
        headers=headers,
        json={"photo_id": photo_id, "notes": "Rakovi na grančicama na istočnoj strani."},
    )
    assert analysis.status_code == 201, analysis.text
    payload = analysis.json()
    assert payload["likely_issue"]
    issue = payload["likely_issue"].lower()
    assert any(word in issue for word in ("rak", "canker", "blight"))
    assert "weevil" not in issue and "žižak" not in issue
    disclaimer = (payload["disclaimer"] + " " + payload["uncertainty_notes"]).lower()
    assert any(word in disclaimer for word in ("nije potvrđen", "not a confirmed", "dijagnoz", "diagnos"))
    assert payload["supporting_sources"] is not None
    assert "dose" not in payload["recommended_next_step"].lower()
    listed = client.get(f"/api/v1/ai/disease-cases/{blight['id']}/analyses", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    deleted = client.delete(f"/api/v1/knowledge/documents/{probe_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    print("Knowledge and AI verification passed.")


if __name__ == "__main__":
    verify_knowledge_and_ai()
