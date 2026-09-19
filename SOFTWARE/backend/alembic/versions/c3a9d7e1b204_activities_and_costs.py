"""activities and costs

Revision ID: c3a9d7e1b204
Revises: 8c2a1b4e7f01
Create Date: 2026-09-14 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3a9d7e1b204"
down_revision: Union[str, Sequence[str], None] = "8c2a1b4e7f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activity_types",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("activities", sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column("activities", sa.Column("unit", sa.String(length=32), nullable=True))

    op.create_table(
        "cost_categories",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    op.add_column("costs", sa.Column("cost_category_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("costs", sa.Column("receipt_filename", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_costs_cost_category_id",
        "costs",
        "cost_categories",
        ["cost_category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_index(op.f("ix_costs_category"), table_name="costs")
    op.drop_column("costs", "category")
    op.alter_column("costs", "cost_category_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_index(op.f("ix_costs_cost_category_id"), "costs", ["cost_category_id"], unique=False)

    op.drop_constraint("costs_activity_id_fkey", "costs", type_="foreignkey")
    op.alter_column("costs", "activity_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "fk_costs_activity_id",
        "costs",
        "activities",
        ["activity_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute("DROP TYPE IF EXISTS cost_category")


def downgrade() -> None:
    cost_category = postgresql.ENUM(
        "labor",
        "materials",
        "machinery",
        "planting",
        "protection",
        "fertilization",
        "irrigation",
        "harvest",
        "other",
        name="cost_category",
    )
    cost_category.create(op.get_bind(), checkfirst=True)

    op.drop_constraint("fk_costs_activity_id", "costs", type_="foreignkey")
    op.alter_column("costs", "activity_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_foreign_key(
        "costs_activity_id_fkey",
        "costs",
        "activities",
        ["activity_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "costs",
        sa.Column(
            "category",
            postgresql.ENUM(
                "labor",
                "materials",
                "machinery",
                "planting",
                "protection",
                "fertilization",
                "irrigation",
                "harvest",
                "other",
                name="cost_category",
                create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
    )
    op.create_index(op.f("ix_costs_category"), "costs", ["category"], unique=False)
    op.drop_index(op.f("ix_costs_cost_category_id"), table_name="costs")
    op.drop_constraint("fk_costs_cost_category_id", "costs", type_="foreignkey")
    op.drop_column("costs", "receipt_filename")
    op.drop_column("costs", "cost_category_id")
    op.drop_table("cost_categories")
    op.drop_column("activities", "unit")
    op.drop_column("activities", "quantity")
    op.drop_column("activity_types", "sort_order")
