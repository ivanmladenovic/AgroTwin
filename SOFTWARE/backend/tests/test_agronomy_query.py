from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.knowledge.pdf import build_text_pdf
from app.main import app
from app.models.enums import KnowledgeCategory
from app.services.knowledge import KnowledgeService
from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import select


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class AgronomyQueryApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def test_out_of_scope_does_not_invent_answer(self) -> None:
        response = self.client.post(
            "/api/v1/ai/agronomy/query",
            headers=self.headers,
            json={"question": "Koji je glavni grad Francuske?", "mode": "retrieve", "debug": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["out_of_scope"])
        self.assertFalse(body["sufficient_evidence"])
        self.assertIn("AgroTwin bazi znanja", body["answer"])

    def test_unknown_product_price_is_insufficient(self) -> None:
        response = self.client.post(
            "/api/v1/ai/agronomy/query",
            headers=self.headers,
            json={"question": "Koja je cena proizvoda X?", "mode": "retrieve"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertFalse(body["sufficient_evidence"])
        self.assertTrue("agronomom" in body["answer"].lower() or "bazi znanja" in body["answer"].lower())

    def test_unauthorized_query_rejected(self) -> None:
        response = self.client.post("/api/v1/ai/agronomy/query", json={"question": "Koja je uloga azota kod leske?"})
        self.assertEqual(response.status_code, 401)

    def test_ingested_text_manual_is_retrievable(self) -> None:
        db = SessionLocal()
        try:
            user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
            assert user is not None
            pdf = build_text_pdf(
                "Priručnik - Ishrana leske",
                [
                    (
                        "Makroelementi",
                        "Kalijum ima važnu ulogu u otpornosti leske i u transportu asimilata. "
                        "Simptomi nedostatka kalijuma su ivice lista koje se suše. "
                        "Azot utiče na vegetativni rast leske.",
                    )
                ],
            )
            service = KnowledgeService(db)
            document = service.ingest_or_skip(
                user.id,
                filename=f"Prirucnik - Ishrana leske-{uuid4().hex[:6]}.pdf",
                content=pdf,
                title="Priručnik - Ishrana leske",
                category=KnowledgeCategory.NUTRITION_GUIDE,
                uploaded_by_id=user.id,
                source_kind="agriser_manual",
                force=True,
            )
            self.assertEqual(document.status.value, "ready")
            self.assertGreater(document.chunk_count, 0)
            doc_id = str(document.id)
        finally:
            db.close()

        try:
            response = self.client.post(
                "/api/v1/ai/agronomy/query",
                headers=self.headers,
                json={"question": "Koja je uloga kalijuma kod leske?", "mode": "retrieve", "debug": True},
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertTrue(body["sufficient_evidence"], body)
            self.assertIn("kalij", body["answer"].lower())
            self.assertEqual(body["debug"]["detected_domain"], "nutrition")
        finally:
            self.client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=self.headers)
