"""activity semantic types and observation links for planning

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-10-06 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, Sequence[str], None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    semantic = postgresql.ENUM(
        "observation",
        "problem",
        "treatment",
        "fertilization",
        "irrigation",
        "monitoring",
        "pruning",
        "planting",
        "other",
        name="activity_semantic_type",
    )
    obs_category = postgresql.ENUM(
        "disease",
        "pest",
        "nutrient",
        "weather_damage",
        "water_stress",
        "tree_health",
        "fruit",
        "leaf",
        "soil",
        "other",
        "unknown",
        name="observation_category",
    )
    obs_status = postgresql.ENUM(
        "new",
        "monitoring",
        "confirmed",
        "resolved",
        "rejected",
        "unknown",
        name="observation_status",
    )
    bind = op.get_bind()
    semantic.create(bind, checkfirst=True)
    obs_category.create(bind, checkfirst=True)
    obs_status.create(bind, checkfirst=True)

    op.add_column(
        "activities",
        sa.Column(
            "semantic_type",
            postgresql.ENUM(
                "observation",
                "problem",
                "treatment",
                "fertilization",
                "irrigation",
                "monitoring",
                "pruning",
                "planting",
                "other",
                name="activity_semantic_type",
                create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
    )
    op.add_column(
        "activities",
        sa.Column(
            "observation_category",
            postgresql.ENUM(
                "disease",
                "pest",
                "nutrient",
                "weather_damage",
                "water_stress",
                "tree_health",
                "fruit",
                "leaf",
                "soil",
                "other",
                "unknown",
                name="observation_category",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    # Reuse existing disease_severity enum; do not invent new severity values.
    op.add_column(
        "activities",
        sa.Column(
            "observation_severity",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "critical",
                name="disease_severity",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "activities",
        sa.Column(
            "observation_status",
            postgresql.ENUM(
                "new",
                "monitoring",
                "confirmed",
                "resolved",
                "rejected",
                "unknown",
                name="observation_status",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("activities", sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("activities", sa.Column("plan_item_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("activities", sa.Column("follow_up_of_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_index(op.f("ix_activities_semantic_type"), "activities", ["semantic_type"], unique=False)
    op.create_index(op.f("ix_activities_observation_category"), "activities", ["observation_category"], unique=False)
    op.create_index(op.f("ix_activities_observation_status"), "activities", ["observation_status"], unique=False)
    op.create_index(op.f("ix_activities_observation_id"), "activities", ["observation_id"], unique=False)
    op.create_index(op.f("ix_activities_plan_item_id"), "activities", ["plan_item_id"], unique=False)
    op.create_index(op.f("ix_activities_follow_up_of_id"), "activities", ["follow_up_of_id"], unique=False)

    op.create_foreign_key(
        "fk_activities_observation_id",
        "activities",
        "activities",
        ["observation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_activities_follow_up_of_id",
        "activities",
        "activities",
        ["follow_up_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_activities_plan_item_id",
        "activities",
        "planning_plan_items",
        ["plan_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Safe backfill from catalog slug only — never invent observation categories from free text.
    op.execute(
        """
        UPDATE activities AS a
        SET semantic_type = CASE at.slug
            WHEN 'irrigation' THEN 'irrigation'::activity_semantic_type
            WHEN 'fertilization' THEN 'fertilization'::activity_semantic_type
            WHEN 'pruning' THEN 'pruning'::activity_semantic_type
            WHEN 'planting' THEN 'planting'::activity_semantic_type
            WHEN 'spraying' THEN 'treatment'::activity_semantic_type
            WHEN 'disease_treatment' THEN 'treatment'::activity_semantic_type
            WHEN 'inspection' THEN 'monitoring'::activity_semantic_type
            ELSE 'other'::activity_semantic_type
        END
        FROM activity_types AS at
        WHERE a.activity_type_id = at.id
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_activities_plan_item_id", "activities", type_="foreignkey")
    op.drop_constraint("fk_activities_follow_up_of_id", "activities", type_="foreignkey")
    op.drop_constraint("fk_activities_observation_id", "activities", type_="foreignkey")
    op.drop_index(op.f("ix_activities_follow_up_of_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_plan_item_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_observation_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_observation_status"), table_name="activities")
    op.drop_index(op.f("ix_activities_observation_category"), table_name="activities")
    op.drop_index(op.f("ix_activities_semantic_type"), table_name="activities")
    op.drop_column("activities", "follow_up_of_id")
    op.drop_column("activities", "plan_item_id")
    op.drop_column("activities", "observation_id")
    op.drop_column("activities", "observation_status")
    op.drop_column("activities", "observation_severity")
    op.drop_column("activities", "observation_category")
    op.drop_column("activities", "semantic_type")
    op.execute("DROP TYPE IF EXISTS observation_status")
    op.execute("DROP TYPE IF EXISTS observation_category")
    op.execute("DROP TYPE IF EXISTS activity_semantic_type")
