"""tree health observations and photos

Revision ID: d4b8e2c1a305
Revises: c3a9d7e1b204
Create Date: 2026-09-14 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4b8e2c1a305"
down_revision: Union[str, Sequence[str], None] = "c3a9d7e1b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE disease_case_status ADD VALUE IF NOT EXISTS 'unknown'")
        op.execute("ALTER TYPE attachment_entity_type ADD VALUE IF NOT EXISTS 'observation'")

    disease_category = postgresql.ENUM(
        "disease",
        "pest",
        "nutrient_deficiency",
        "water_stress",
        "physical_damage",
        "unknown",
        "other",
        name="disease_category",
    )
    disease_category.create(op.get_bind(), checkfirst=True)

    op.add_column("disease_cases", sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("disease_cases", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("disease_cases", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "disease_cases",
        sa.Column(
            "category",
            postgresql.ENUM(
                "disease",
                "pest",
                "nutrient_deficiency",
                "water_stress",
                "physical_damage",
                "unknown",
                "other",
                name="disease_category",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("disease_cases", sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE disease_cases SET title = name WHERE title IS NULL")
    op.alter_column("disease_cases", "title", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("disease_cases", "tree_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.drop_column("disease_cases", "name")
    op.create_index(op.f("ix_disease_cases_row_id"), "disease_cases", ["row_id"], unique=False)
    op.create_index(op.f("ix_disease_cases_category"), "disease_cases", ["category"], unique=False)
    op.create_foreign_key(
        "fk_disease_cases_row_id",
        "disease_cases",
        "orchard_rows",
        ["row_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_disease_cases_created_by_id",
        "disease_cases",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "disease_observations",
        sa.Column("disease_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["disease_case_id"], ["disease_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_disease_observations_disease_case_id"), "disease_observations", ["disease_case_id"], unique=False)
    op.create_index(op.f("ix_disease_observations_observed_on"), "disease_observations", ["observed_on"], unique=False)

    op.add_column("photos", sa.Column("storage_key", sa.String(length=512), nullable=True))
    op.add_column("photos", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE photos SET storage_key = storage_path WHERE storage_key IS NULL")
    op.alter_column("photos", "storage_key", existing_type=sa.String(length=512), nullable=False)
    op.drop_column("photos", "storage_path")


def downgrade() -> None:
    op.add_column("photos", sa.Column("storage_path", sa.String(length=512), nullable=True))
    op.execute("UPDATE photos SET storage_path = storage_key")
    op.alter_column("photos", "storage_path", existing_type=sa.String(length=512), nullable=False)
    op.drop_column("photos", "size_bytes")
    op.drop_column("photos", "storage_key")

    op.drop_index(op.f("ix_disease_observations_observed_on"), table_name="disease_observations")
    op.drop_index(op.f("ix_disease_observations_disease_case_id"), table_name="disease_observations")
    op.drop_table("disease_observations")

    op.add_column("disease_cases", sa.Column("name", sa.String(length=255), nullable=True))
    op.execute("UPDATE disease_cases SET name = title")
    op.alter_column("disease_cases", "name", existing_type=sa.String(length=255), nullable=False)
    op.drop_constraint("fk_disease_cases_created_by_id", "disease_cases", type_="foreignkey")
    op.drop_constraint("fk_disease_cases_row_id", "disease_cases", type_="foreignkey")
    op.drop_index(op.f("ix_disease_cases_category"), table_name="disease_cases")
    op.drop_index(op.f("ix_disease_cases_row_id"), table_name="disease_cases")
    op.drop_column("disease_cases", "created_by_id")
    op.drop_column("disease_cases", "category")
    op.drop_column("disease_cases", "description")
    op.drop_column("disease_cases", "title")
    op.drop_column("disease_cases", "row_id")
    op.alter_column("disease_cases", "tree_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    postgresql.ENUM(name="disease_category").drop(op.get_bind(), checkfirst=True)
