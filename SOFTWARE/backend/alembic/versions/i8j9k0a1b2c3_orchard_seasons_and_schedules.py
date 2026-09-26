"""orchard seasons and recurring task schedules

Revision ID: i8j9k0a1b2c3
Revises: h7i8j9k0a1b2
Create Date: 2026-09-25 08:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "i8j9k0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orchard_seasons",
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_orchard_seasons_range"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orchard_seasons_farm_id"), "orchard_seasons", ["farm_id"], unique=False)
    op.create_index(op.f("ix_orchard_seasons_parcel_id"), "orchard_seasons", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_orchard_seasons_starts_on"), "orchard_seasons", ["starts_on"], unique=False)
    op.create_index(op.f("ix_orchard_seasons_ends_on"), "orchard_seasons", ["ends_on"], unique=False)

    op.create_table(
        "task_schedules",
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activity_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("weekdays", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_task_schedules_range"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["season_id"], ["orchard_seasons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["activity_type_id"], ["activity_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_schedules_farm_id"), "task_schedules", ["farm_id"], unique=False)
    op.create_index(op.f("ix_task_schedules_parcel_id"), "task_schedules", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_task_schedules_season_id"), "task_schedules", ["season_id"], unique=False)
    op.create_index(op.f("ix_task_schedules_activity_type_id"), "task_schedules", ["activity_type_id"], unique=False)
    op.create_index(op.f("ix_task_schedules_starts_on"), "task_schedules", ["starts_on"], unique=False)
    op.create_index(op.f("ix_task_schedules_ends_on"), "task_schedules", ["ends_on"], unique=False)

    op.add_column("activities", sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_activities_schedule_id"), "activities", ["schedule_id"], unique=False)
    op.create_foreign_key(
        "fk_activities_schedule_id_task_schedules",
        "activities",
        "task_schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_activities_schedule_id_task_schedules", "activities", type_="foreignkey")
    op.drop_index(op.f("ix_activities_schedule_id"), table_name="activities")
    op.drop_column("activities", "schedule_id")

    op.drop_index(op.f("ix_task_schedules_ends_on"), table_name="task_schedules")
    op.drop_index(op.f("ix_task_schedules_starts_on"), table_name="task_schedules")
    op.drop_index(op.f("ix_task_schedules_activity_type_id"), table_name="task_schedules")
    op.drop_index(op.f("ix_task_schedules_season_id"), table_name="task_schedules")
    op.drop_index(op.f("ix_task_schedules_parcel_id"), table_name="task_schedules")
    op.drop_index(op.f("ix_task_schedules_farm_id"), table_name="task_schedules")
    op.drop_table("task_schedules")

    op.drop_index(op.f("ix_orchard_seasons_ends_on"), table_name="orchard_seasons")
    op.drop_index(op.f("ix_orchard_seasons_starts_on"), table_name="orchard_seasons")
    op.drop_index(op.f("ix_orchard_seasons_parcel_id"), table_name="orchard_seasons")
    op.drop_index(op.f("ix_orchard_seasons_farm_id"), table_name="orchard_seasons")
    op.drop_table("orchard_seasons")
