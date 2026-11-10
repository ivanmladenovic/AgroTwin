"""protection plan item kinds, priority, evidence

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-10-06 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, Sequence[str], None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    item_kind = postgresql.ENUM(
        "monitoring",
        "observation",
        "assessment",
        "expert_review",
        "intervention_pending",
        name="planning_item_kind",
    )
    stream = postgresql.ENUM("preventive", "reactive", name="planning_stream")
    priority_level = postgresql.ENUM("high", "medium", "low", "info", name="planning_priority_level")
    bind = op.get_bind()
    item_kind.create(bind, checkfirst=True)
    stream.create(bind, checkfirst=True)
    priority_level.create(bind, checkfirst=True)

    # Extend existing source enum safely.
    op.execute("ALTER TYPE planning_item_source ADD VALUE IF NOT EXISTS 'history'")

    op.add_column(
        "planning_plan_items",
        sa.Column(
            "priority_level",
            postgresql.ENUM("high", "medium", "low", "info", name="planning_priority_level", create_type=False),
            nullable=False,
            server_default="info",
        ),
    )
    op.add_column("planning_plan_items", sa.Column("priority_reason", sa.Text(), nullable=True))
    op.add_column(
        "planning_plan_items",
        sa.Column(
            "item_kind",
            postgresql.ENUM(
                "monitoring",
                "observation",
                "assessment",
                "expert_review",
                "intervention_pending",
                name="planning_item_kind",
                create_type=False,
            ),
            nullable=False,
            server_default="monitoring",
        ),
    )
    op.add_column(
        "planning_plan_items",
        sa.Column(
            "stream",
            postgresql.ENUM("preventive", "reactive", name="planning_stream", create_type=False),
            nullable=False,
            server_default="preventive",
        ),
    )
    op.add_column("planning_plan_items", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column(
        "planning_plan_items",
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "planning_plan_items",
        sa.Column(
            "missing_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("planning_plan_items", sa.Column("related_activity_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_planning_plan_items_item_kind"), "planning_plan_items", ["item_kind"], unique=False)
    op.create_index(op.f("ix_planning_plan_items_stream"), "planning_plan_items", ["stream"], unique=False)
    op.create_index(
        op.f("ix_planning_plan_items_related_activity_id"),
        "planning_plan_items",
        ["related_activity_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_planning_plan_items_related_activity_id",
        "planning_plan_items",
        "activities",
        ["related_activity_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Map legacy numeric priority into levels without inventing agronomy.
    op.execute(
        """
        UPDATE planning_plan_items
        SET priority_level = CASE
            WHEN priority >= 75 THEN 'high'::planning_priority_level
            WHEN priority >= 40 THEN 'medium'::planning_priority_level
            WHEN priority >= 15 THEN 'low'::planning_priority_level
            ELSE 'info'::planning_priority_level
        END
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_planning_plan_items_related_activity_id", "planning_plan_items", type_="foreignkey")
    op.drop_index(op.f("ix_planning_plan_items_related_activity_id"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_stream"), table_name="planning_plan_items")
    op.drop_index(op.f("ix_planning_plan_items_item_kind"), table_name="planning_plan_items")
    op.drop_column("planning_plan_items", "related_activity_id")
    op.drop_column("planning_plan_items", "missing_data")
    op.drop_column("planning_plan_items", "evidence")
    op.drop_column("planning_plan_items", "reason")
    op.drop_column("planning_plan_items", "stream")
    op.drop_column("planning_plan_items", "item_kind")
    op.drop_column("planning_plan_items", "priority_reason")
    op.drop_column("planning_plan_items", "priority_level")
    op.execute("DROP TYPE IF EXISTS planning_priority_level")
    op.execute("DROP TYPE IF EXISTS planning_stream")
    op.execute("DROP TYPE IF EXISTS planning_item_kind")
