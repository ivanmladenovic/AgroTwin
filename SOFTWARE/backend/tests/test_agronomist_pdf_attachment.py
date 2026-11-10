from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.core.exceptions import AppError
from app.knowledge.pdf import build_text_pdf
from app.services.agronomist import AgronomistService


class _MemoryStorage:
    def __init__(self) -> None:
        self.items: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.items[key] = (content, content_type)

    def get(self, key: str) -> bytes:
        return self.items[key][0]

    def delete(self, key: str) -> None:
        self.items.pop(key, None)


class AgronomistPdfAttachmentTests(TestCase):
    def setUp(self) -> None:
        self.service = AgronomistService.__new__(AgronomistService)
        self.service.storage = _MemoryStorage()
        self.conversation = SimpleNamespace(id=uuid4())

    def test_store_pdf_extracts_text(self) -> None:
        long_body = (
            "Laboratorijska analiza zemljišta za parcelu Leska Sever. "
            "pH vrednost u uzorku iznosi 6.8. Organska materija je 2.4%. "
            "Ukupan azot je umeren. Fosfor (P2O5) je 18 mg/100g, kalijum (K2O) 22 mg/100g. "
            "Preporuka: korekcija pH nije neophodna; planirati đubrenje prema prinosu. "
        ) * 4
        pdf = build_text_pdf(
            "Analiza zemljista",
            [("pH i minerali", long_body), ("Zakljucak", "Ukupan azot je umeren, pH 6.8.")],
        )
        refs, parts, document_text, placeholder = self.service._store_chat_attachment(
            self.conversation,
            payload=pdf,
            filename="analiza.pdf",
            content_type="application/pdf",
        )
        self.assertEqual(placeholder, "Pogledajte priloženi PDF dokument.")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["kind"], "chat_document")
        self.assertTrue(document_text)
        self.assertIn("6.8", document_text)
        self.assertEqual(parts, [])  # enough extracted text → no vision pages

    def test_reject_non_pdf_bytes_with_pdf_name(self) -> None:
        with self.assertRaises(AppError):
            self.service._store_chat_attachment(
                self.conversation,
                payload=b"not-a-pdf",
                filename="fake.pdf",
                content_type="application/pdf",
            )
