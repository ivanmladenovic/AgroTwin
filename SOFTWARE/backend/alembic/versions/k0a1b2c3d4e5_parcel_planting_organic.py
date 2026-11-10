"""parcel planting batches and organic production fields

Revision ID: k0a1b2c3d4e5
Revises: j9k0a1b2c3d4
Create Date: 2026-10-06 09:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "k0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "j9k0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    production_method = postgresql.ENUM("conventional", "organic", name="production_method")
    organic_scope = postgresql.ENUM("none", "entire_parcel", "part_of_parcel", name="organic_scope")
    batch_scope = postgresql.ENUM("parcel", "row", name="planting_batch_scope")
    bind = op.get_bind()
    production_method.create(bind, checkfirst=True)
    organic_scope.create(bind, checkfirst=True)
    batch_scope.create(bind, checkfirst=True)

    op.add_column(
        "parcels",
        sa.Column(
            "production_method",
            postgresql.ENUM("conventional", "organic", name="production_method", create_type=False),
            nullable=False,
            server_default="conventional",
        ),
    )
    op.add_column(
        "parcels",
        sa.Column(
            "organic_scope",
            postgresql.ENUM("none", "entire_parcel", "part_of_parcel", name="organic_scope", create_type=False),
            nullable=False,
            server_default="none",
        ),
    )

    op.add_column("orchard_rows", sa.Column("planting_year", sa.Integer(), nullable=True))
    op.add_column(
        "orchard_rows",
        sa.Column("is_organic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column("trees", sa.Column("is_organic", sa.Boolean(), nullable=True))

    op.create_table(
        "planting_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "scope_type",
            postgresql.ENUM("parcel", "row", name="planting_batch_scope", create_type=False),
            nullable=False,
            server_default="parcel",
        ),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("row_number_from", sa.Integer(), nullable=True),
        sa.Column("row_number_to", sa.Integer(), nullable=True),
        sa.Column("planted_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_planting_batches_quantity_positive"),
        sa.CheckConstraint(
            "(row_number_from IS NULL AND row_number_to IS NULL) OR "
            "(row_number_from IS NOT NULL AND row_number_to IS NOT NULL AND row_number_to >= row_number_from)",
            name="ck_planting_batches_row_range",
        ),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["row_id"], ["orchard_rows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_planting_batches_parcel_id"), "planting_batches", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_planting_batches_year"), "planting_batches", ["year"], unique=False)
    op.create_index(op.f("ix_planting_batches_row_id"), "planting_batches", ["row_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_planting_batches_row_id"), table_name="planting_batches")
    op.drop_index(op.f("ix_planting_batches_year"), table_name="planting_batches")
    op.drop_index(op.f("ix_planting_batches_parcel_id"), table_name="planting_batches")
    op.drop_table("planting_batches")

    op.drop_column("trees", "is_organic")
    op.drop_column("orchard_rows", "is_organic")
    op.drop_column("orchard_rows", "planting_year")
    op.drop_column("parcels", "organic_scope")
    op.drop_column("parcels", "production_method")

    op.execute("DROP TYPE IF EXISTS planting_batch_scope")
    op.execute("DROP TYPE IF EXISTS organic_scope")
    op.execute("DROP TYPE IF EXISTS production_method")
