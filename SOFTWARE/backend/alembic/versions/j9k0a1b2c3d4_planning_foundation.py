"""planning seasons, plans, and plan items foundation

Revision ID: j9k0a1b2c3d4
Revises: i8j9k0a1b2c3
Create Date: 2026-10-06 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "j9k0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "i8j9k0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    season_status = postgresql.ENUM(
        "draft", "active", "completed", "archived",
        name="planning_season_status",
    )
    plan_type = postgresql.ENUM(
        "protection", "nutrition", "irrigation",
        name="planning_plan_type",
    )
    plan_status = postgresql.ENUM(
        "draft",
        "ready_for_review",
        "expert_review",
        "approved",
        "rejected",
        "active",
        "completed",
        name="planning_plan_status",
    )
    item_status = postgresql.ENUM(
        "planned",
        "monitor",
        "observed",
        "needs_review",
        "approved",
        "completed",
        "cancelled",
        name="planning_item_status",
    )
    item_source = postgresql.ENUM(
        "system",
        "agronomic_rule",
        "previous_plan",
        "user",
        "ai",
        name="planning_item_source",
    )
    expert_status = postgresql.ENUM(
        "not_required",
        "pending",
        "approved",
        "modified",
        "rejected",
        name="planning_expert_review_status",
    )
    scope_type = postgresql.ENUM(
        "parcel", "row", "tree",
        name="planning_scope_type",
    )

    bind = op.get_bind()
    season_status.create(bind, checkfirst=True)
    plan_type.create(bind, checkfirst=True)
    plan_status.create(bind, checkfirst=True)
    item_status.create(bind, checkfirst=True)
    item_source.create(bind, checkfirst=True)
    expert_status.create(bind, checkfirst=True)
    scope_type.create(bind, checkfirst=True)

    op.create_table(
        "planning_seasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "active", "completed", "archived",
                name="planning_season_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("copied_from_season_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["copied_from_season_id"], ["planning_seasons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parcel_id", "year", name="uq_planning_seasons_parcel_year"),
    )
    op.create_index(op.f("ix_planning_seasons_farm_id"), "planning_seasons", ["farm_id"], unique=False)
    op.create_index(op.f("ix_planning_seasons_parcel_id"), "planning_seasons", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_planning_seasons_year"), "planning_seasons", ["year"], unique=False)
    op.create_index(
        op.f("ix_planning_seasons_copied_from_season_id"),
        "planning_seasons",
        ["copied_from_season_id"],
        unique=False,
    )

    op.create_table(
        "planning_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "protection", "nutrition", "irrigation",
                name="planning_plan_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "ready_for_review",
                "expert_review",
                "approved",
                "rejected",
                "active",
                "completed",
                name="planning_plan_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["planning_season_id"], ["planning_seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "planning_season_id",
            "type",
            "version",
            name="uq_planning_plans_season_type_version",
        ),
    )
    op.create_index(op.f("ix_planning_plans_planning_season_id"), "planning_plans", ["planning_season_id"], unique=False)
    op.create_index(op.f("ix_planning_plans_type"), "planning_plans", ["type"], unique=False)

    op.create_table(
        "planning_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scope_type",
            postgresql.ENUM("parcel", "row", "tree", name="planning_scope_type", create_type=False),
            nullable=False,
        ),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planned_date_from", sa.Date(), nullable=True),
        sa.Column("planned_date_to", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "planned",
                "monitor",
                "observed",
                "needs_review",
                "approved",
                "completed",
                "cancelled",
                name="planning_item_status",
                create_type=False,
            ),
            nullable=False,
            server_default="planned",
        ),
        sa.Column(
            "source",
            postgresql.ENUM(
                "system",
                "agronomic_rule",
                "previous_plan",
                "user",
                "ai",
                name="planning_item_source",
                create_type=False,
            ),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "expert_review_status",
            postgresql.ENUM(
                "not_required",
                "pending",
                "approved",
                "modified",
                "rejected",
                name="planning_expert_review_status",
                create_type=False,
            ),
            nullable=False,
            server_default="not_required",
        ),
        sa.Column("source_season_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_plan_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["planning_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_season_id"], ["planning_seasons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_plan_id"], ["planning_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_plan_item_id"], ["planning_plan_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_planning_plan_items_plan_id"), "planning_plan_items", ["plan_id"], unique=False)
    op.create_index(op.f("ix_planning_plan_items_scope_type"), "planning_plan_items", ["scope_type"], unique=False)
    op.create_index(op.f("ix_planning_plan_items_scope_id"), "planning_plan_items", ["scope_id"], unique=False)
    op.create_index(
        op.f("ix_planning_plan_items_source_season_id"),
        "planning_plan_items",
        ["source_season_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_planning_plan_items_source_plan_id"),
        "planning_plan_items",
        ["source_plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_planning_plan_items_source_plan_item_id"),
        "planning_plan_items",
        ["source_plan_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_planning_plan_items_source_plan_item_id"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_source_plan_id"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_source_season_id"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_scope_id"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_scope_type"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_plan_id"), table_name="planning_plan_items")
    op.drop_table("planning_plan_items")

    op.drop_index(op.f("ix_planning_plans_type"), table_name="planning_plans")
    op.drop_index(op.f("ix_planning_plans_planning_season_id"), table_name="planning_plans")
    op.drop_table("planning_plans")

    op.drop_index(op.f("ix_planning_seasons_copied_from_season_id"), table_name="planning_seasons")
    op.drop_index(op.f("ix_planning_seasons_year"), table_name="planning_seasons")
    op.drop_index(op.f("ix_planning_seasons_parcel_id"), table_name="planning_seasons")
    op.drop_index(op.f("ix_planning_seasons_farm_id"), table_name="planning_seasons")
    op.drop_table("planning_seasons")

    op.execute("DROP TYPE IF EXISTS planning_scope_type")
    op.execute("DROP TYPE IF EXISTS planning_expert_review_status")
    op.execute("DROP TYPE IF EXISTS planning_item_source")
    op.execute("DROP TYPE IF EXISTS planning_item_status")
    op.execute("DROP TYPE IF EXISTS planning_plan_status")
    op.execute("DROP TYPE IF EXISTS planning_plan_type")
    op.execute("DROP TYPE IF EXISTS planning_season_status")
