from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import InvoiceCategory, InvoiceKind, pg_enum


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[InvoiceCategory] = mapped_column(
        pg_enum(InvoiceCategory, "invoice_category"),
        nullable=False,
        index=True,
    )
    kind: Mapped[InvoiceKind | None] = mapped_column(
        pg_enum(InvoiceKind, "invoice_kind"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
