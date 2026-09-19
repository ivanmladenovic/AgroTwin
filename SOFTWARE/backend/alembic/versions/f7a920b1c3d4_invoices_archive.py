"""invoices archive for fuel and other receipts

Revision ID: f7a920b1c3d4
Revises: e6f819a0b1c2
Create Date: 2026-09-14 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f7a920b1c3d4"
down_revision: Union[str, Sequence[str], None] = "e6f819a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    invoice_category = postgresql.ENUM("fuel", "other", name="invoice_category")
    invoice_kind = postgresql.ENUM("machine", "equipment", "other", name="invoice_kind")
    invoice_category.create(op.get_bind(), checkfirst=True)
    invoice_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "invoices",
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM("fuel", "other", name="invoice_category", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "kind",
            postgresql.ENUM("machine", "equipment", "other", name="invoice_kind", create_type=False),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoices_farm_id"), "invoices", ["farm_id"], unique=False)
    op.create_index(op.f("ix_invoices_category"), "invoices", ["category"], unique=False)
    op.create_index(op.f("ix_invoices_kind"), "invoices", ["kind"], unique=False)
    op.create_index(op.f("ix_invoices_issued_on"), "invoices", ["issued_on"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoices_issued_on"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_kind"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_category"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_farm_id"), table_name="invoices")
    op.drop_table("invoices")
    postgresql.ENUM(name="invoice_kind").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="invoice_category").drop(op.get_bind(), checkfirst=True)
