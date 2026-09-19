from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import InvoiceCategory
from app.models.invoice import Invoice


class InvoiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_farm(self, farm_id: UUID, category: InvoiceCategory | None = None) -> list[Invoice]:
        stmt = select(Invoice).where(Invoice.farm_id == farm_id)
        if category is not None:
            stmt = stmt.where(Invoice.category == category)
        stmt = stmt.order_by(Invoice.issued_on.desc(), Invoice.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_for_farm(self, invoice_id: UUID, farm_id: UUID) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.farm_id == farm_id)
        return self.db.scalars(stmt).first()

    def add(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        return invoice

    def delete(self, invoice: Invoice) -> None:
        self.db.delete(invoice)
