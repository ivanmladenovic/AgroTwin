"""Enterprise otkup: supplier prices and purchase records.

Revision ID: z5a6b7c8d9e0
Revises: y4z5a6b7c8d9
Create Date: 2026-10-16 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "z5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "y4z5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_supplier_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RSD"),
        sa.Column("price_bruto_per_kg", sa.Numeric(14, 4), nullable=True),
        sa.Column("price_neto_per_kg", sa.Numeric(14, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "farm_id",
            "season_year",
            name="uq_enterprise_supplier_price_org_farm_year",
        ),
    )
    op.create_index(
        "ix_enterprise_supplier_prices_organization_id",
        "enterprise_supplier_prices",
        ["organization_id"],
    )
    op.create_index(
        "ix_enterprise_supplier_prices_farm_id",
        "enterprise_supplier_prices",
        ["farm_id"],
    )
    op.create_index(
        "ix_enterprise_supplier_prices_season_year",
        "enterprise_supplier_prices",
        ["season_year"],
    )

    op.create_table(
        "enterprise_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("purchased_on", sa.Date(), nullable=False),
        sa.Column("quantity_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("quantity_basis", sa.String(length=16), nullable=False, server_default="bruto"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RSD"),
        sa.Column("unit_price_per_kg", sa.Numeric(14, 4), nullable=False),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("price_bruto_per_kg", sa.Numeric(14, 4), nullable=True),
        sa.Column("price_neto_per_kg", sa.Numeric(14, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_enterprise_purchases_organization_id",
        "enterprise_purchases",
        ["organization_id"],
    )
    op.create_index("ix_enterprise_purchases_farm_id", "enterprise_purchases", ["farm_id"])
    op.create_index(
        "ix_enterprise_purchases_purchased_on",
        "enterprise_purchases",
        ["purchased_on"],
    )


def downgrade() -> None:
    op.drop_table("enterprise_purchases")
    op.drop_table("enterprise_supplier_prices")
