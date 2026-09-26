from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.enums import InvoiceCategory, InvoiceKind
from app.models.farm import Farm
from app.models.invoice import Invoice
from app.repositories.farm import FarmRepository
from app.repositories.invoice import InvoiceRepository
from app.schemas.invoice import InvoiceRead
from app.storage import get_storage
from app.storage.images import compress_photo

MAX_FILE_BYTES = 15 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/x-pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class InvoiceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.invoices = InvoiceRepository(db)
        self.farms = FarmRepository(db)
        self.storage = get_storage()

    def list_invoices(self, owner_id: UUID, category: InvoiceCategory | None = None) -> list[InvoiceRead]:
        farm = self._farm(owner_id)
        return [self.to_read(item) for item in self.invoices.list_for_farm(farm.id, category)]

    def get_invoice(self, invoice_id: UUID, owner_id: UUID) -> Invoice:
        farm = self._farm(owner_id)
        invoice = self.invoices.get_for_farm(invoice_id, farm.id)
        if invoice is None:
            raise NotFoundError("Račun nije pronađen")
        return invoice

    def create(
        self,
        owner_id: UUID,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        title: str,
        category: InvoiceCategory,
        kind: InvoiceKind | None,
        vendor: str | None,
        amount: str | None,
        issued_on: date,
        notes: str | None,
        created_by_id: UUID,
    ) -> Invoice:
        extension = self._extension(filename, content_type)
        if len(content) > MAX_FILE_BYTES:
            raise AppError("Datoteka je veća od 15 MB", status_code=422, code="file_too_large")
        if not content:
            raise AppError("Datoteka je prazna", status_code=422, code="empty_file")
        farm = self._farm(owner_id)
        stored_type = "application/pdf" if extension == "pdf" else content_type
        if extension != "pdf":
            compressed = compress_photo(content, filename)
            content = compressed.content
            stored_type = compressed.content_type
            filename = compressed.filename
            extension = compressed.extension.lstrip(".")
        key = f"invoices/{farm.id}/{uuid4().hex}.{extension}"
        self.storage.put(key, content, stored_type)
        invoice = Invoice(
            farm_id=farm.id,
            category=category,
            kind=None if category == InvoiceCategory.FUEL else (kind or InvoiceKind.OTHER),
            title=(title or filename).strip() or filename,
            vendor=(vendor or "").strip() or None,
            amount=self._parse_amount(amount),
            currency="EUR",
            issued_on=issued_on,
            notes=(notes or "").strip() or None,
            storage_key=key,
            original_filename=filename,
            content_type=stored_type,
            size_bytes=len(content),
            created_by_id=created_by_id,
        )
        self.invoices.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def delete(self, invoice_id: UUID, owner_id: UUID) -> None:
        invoice = self.get_invoice(invoice_id, owner_id)
        self.storage.delete(invoice.storage_key)
        self.invoices.delete(invoice)
        self.db.commit()

    def file_local_path(self, invoice: Invoice) -> Path | None:
        return self.storage.local_path(invoice.storage_key)

    def file_bytes(self, invoice: Invoice) -> tuple[bytes, str]:
        return self.storage.get(invoice.storage_key), invoice.content_type

    def to_read(self, invoice: Invoice) -> InvoiceRead:
        return InvoiceRead.model_validate(invoice)

    def _farm(self, owner_id: UUID) -> Farm:
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]

    def _extension(self, filename: str, content_type: str) -> str:
        mapped = ALLOWED_TYPES.get((content_type or "").lower())
        if mapped:
            return mapped
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix in {"pdf", "jpg", "jpeg", "png", "webp"}:
            return "jpg" if suffix == "jpeg" else suffix
        raise AppError(
            "Prihvataju se PDF, JPG, PNG ili WEBP datoteke",
            status_code=422,
            code="invalid_file",
        )

    def _parse_amount(self, value: str | None) -> Decimal | None:
        if value is None or not str(value).strip():
            return None
        try:
            amount = Decimal(str(value).replace(",", ".").strip())
        except (InvalidOperation, ValueError) as exc:
            raise AppError("Iznos nije ispravan", status_code=422, code="invalid_amount") from exc
        if amount < 0:
            raise AppError("Iznos ne može biti negativan", status_code=422, code="invalid_amount")
        return amount.quantize(Decimal("0.01"))
