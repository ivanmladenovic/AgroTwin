from __future__ import annotations

from pathlib import Path
from unittest import TestCase
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


class KnowledgeDocumentApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)
        documents = cls.client.get("/api/v1/knowledge/documents", headers=cls.headers)
        if documents.status_code != 200:
            raise AssertionError(documents.text)
        payload = documents.json()
        if not payload:
            raise AssertionError("Nema priručnika")
        cls.document = payload[0]

    def test_document_file_can_be_opened(self) -> None:
        response = self.client.get(
            f"/api/v1/knowledge/documents/{self.document['id']}/file",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text[:300])
        self.assertIn("pdf", (response.headers.get("content-type") or "").lower())
        self.assertGreater(len(response.content), 100)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_document_page_file_returns_image(self) -> None:
        page = self.client.get(
            f"/api/v1/knowledge/documents/{self.document['id']}/pages/1/file",
            headers=self.headers,
        )
        self.assertEqual(page.status_code, 200, page.text[:300])
        self.assertIn("image", (page.headers.get("content-type") or "").lower())
        self.assertGreater(len(page.content), 100)

    def test_missing_page_returns_404(self) -> None:
        missing = self.client.get(
            f"/api/v1/knowledge/documents/{self.document['id']}/pages/9999/file",
            headers=self.headers,
        )
        self.assertEqual(missing.status_code, 404)

    def test_search_returns_hits_for_nutrition_term(self) -> None:
        response = self.client.get(
            "/api/v1/knowledge/search",
            headers=self.headers,
            params={"q": "lesk"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        hits = response.json()["hits"]
        self.assertGreater(len(hits), 0)
        self.assertTrue(hits[0]["document_title"])
        self.assertTrue(hits[0]["content"])
