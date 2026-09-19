from pathlib import Path
import json
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.main import app
from app.models.enums import DocumentStatus
from app.db.session import SessionLocal
from app.models.document import Document
from sqlalchemy import select

QUESTIONS = [
    "Koja je uloga azota kod leske?",
    "Koji su simptomi nedostatka bora?",
    "Kako se vrši đubrenje pre sadnje?",
    "Kako pripremiti zemljište pre podizanja zasada?",
    "Koje rastojanje treba koristiti pri sadnji?",
    "Kako se vrši rezidba leske?",
    "Kako navodnjavati lesku?",
    "Koje gljivične bolesti napadaju lesku?",
    "Kako prepoznati štetu od mraza?",
    "Koji je kalendar zaštite za mlada stabla?",
    "Kako ishrana utiče na zdravlje i otpornost leske?",
    "Koja je cena proizvoda X?",
    "Koji je glavni grad Francuske?",
]


def main() -> None:
    db = SessionLocal()
    try:
        docs = list(
            db.scalars(select(Document).where(Document.source_kind == "agriser_manual").order_by(Document.title)).all()
        )
        print("=== DOCUMENTS ===")
        for document in docs:
            print(
                json.dumps(
                    {
                        "title": document.title,
                        "status": document.status.value if isinstance(document.status, DocumentStatus) else str(document.status),
                        "pages": document.page_count,
                        "chunks": document.chunk_count,
                        "images": document.image_count,
                        "ocr": document.ocr_version,
                        "parser": document.parser_version,
                        "hash": document.content_sha256,
                        "error": document.error_message,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        db.close()

    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    print("\n=== RETRIEVAL ===")
    for question in QUESTIONS:
        response = client.post(
            "/api/v1/ai/agronomy/query",
            headers=headers,
            json={"question": question, "mode": "retrieve", "debug": True},
        )
        body = response.json()
        debug = body.get("debug") or {}
        sources = (body.get("evidence") or {}).get("sources") or []
        print("\nQ:", question)
        print(
            json.dumps(
                {
                    "status": response.status_code,
                    "sufficient": body.get("sufficient_evidence"),
                    "out_of_scope": body.get("out_of_scope"),
                    "domain": debug.get("detected_domain"),
                    "topic": debug.get("detected_topic"),
                    "documents": debug.get("searched_documents"),
                    "sections": debug.get("searched_sections"),
                    "level": debug.get("level"),
                    "retrieved": debug.get("retrieved_chunks"),
                    "selected": debug.get("selected_chunks"),
                    "confidence": debug.get("confidence"),
                    "pages": [item.get("pages") for item in sources[:4]],
                    "source_sections": [item.get("section") for item in sources[:4]],
                    "answer_preview": (body.get("answer") or "")[:280],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
