from datetime import date
from decimal import Decimal
from uuid import UUID

from app.models.enums import InvoiceCategory, InvoiceKind
from app.schemas.common import IDSchema


class InvoiceRead(IDSchema):
    farm_id: UUID
    category: InvoiceCategory
    kind: InvoiceKind | None
    title: str
    vendor: str | None
    amount: Decimal | None
    currency: str
    issued_on: date
    notes: str | None
    original_filename: str
    content_type: str
    size_bytes: int | None
    created_by_id: UUID | None
