"""workforce workers, task types, work tasks; cost source linkage

Revision ID: u0v1w2x3y4z5
Revises: t9u0v1w2x3y4
Create Date: 2026-10-08 15:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, Sequence[str], None] = "t9u0v1w2x3y4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cost_source = postgresql.ENUM("activity", "work_task", name="cost_source", create_type=False)
    work_task_status = postgresql.ENUM(
        "planned", "completed", "cancelled", name="work_task_status", create_type=False
    )
    postgresql.ENUM("activity", "work_task", name="cost_source").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("planned", "completed", "cancelled", name="work_task_status").create(
        op.get_bind(), checkfirst=True
    )

    op.alter_column("costs", "activity_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("costs", sa.Column("source", cost_source, nullable=True))
    op.add_column("costs", sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_costs_source", "costs", ["source"])
    op.create_index("ix_costs_source_id", "costs", ["source_id"])
    op.execute(
        """
        UPDATE costs
        SET source = 'activity', source_id = activity_id
        WHERE activity_id IS NOT NULL AND source IS NULL
        """
    )
    op.create_check_constraint(
        "ck_costs_activity_or_source",
        "costs",
        "(activity_id IS NOT NULL) OR (source IS NOT NULL AND source_id IS NOT NULL)",
    )

    op.create_table(
        "work_task_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workers_farm_id", "workers", ["farm_id"])

    op.create_table(
        "work_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("worked_on", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("hourly_rate_snapshot", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("labor_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", work_task_status, nullable=False),
        sa.Column("cost_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_type_id"], ["work_task_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cost_id"], ["costs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_tasks_farm_id", "work_tasks", ["farm_id"])
    op.create_index("ix_work_tasks_parcel_id", "work_tasks", ["parcel_id"])
    op.create_index("ix_work_tasks_worker_id", "work_tasks", ["worker_id"])
    op.create_index("ix_work_tasks_task_type_id", "work_tasks", ["task_type_id"])
    op.create_index("ix_work_tasks_worked_on", "work_tasks", ["worked_on"])
    op.create_index("ix_work_tasks_status", "work_tasks", ["status"])
    op.create_index("ix_work_tasks_cost_id", "work_tasks", ["cost_id"])


def downgrade() -> None:
    op.drop_index("ix_work_tasks_cost_id", table_name="work_tasks")
    op.drop_index("ix_work_tasks_status", table_name="work_tasks")
    op.drop_index("ix_work_tasks_worked_on", table_name="work_tasks")
    op.drop_index("ix_work_tasks_task_type_id", table_name="work_tasks")
    op.drop_index("ix_work_tasks_worker_id", table_name="work_tasks")
    op.drop_index("ix_work_tasks_parcel_id", table_name="work_tasks")
    op.drop_index("ix_work_tasks_farm_id", table_name="work_tasks")
    op.drop_table("work_tasks")
    op.drop_index("ix_workers_farm_id", table_name="workers")
    op.drop_table("workers")
    op.drop_table("work_task_types")
    op.drop_constraint("ck_costs_activity_or_source", "costs", type_="check")
    op.drop_index("ix_costs_source_id", table_name="costs")
    op.drop_index("ix_costs_source", table_name="costs")
    op.drop_column("costs", "source_id")
    op.drop_column("costs", "source")
    op.execute("UPDATE costs SET activity_id = source_id WHERE activity_id IS NULL")  # best-effort
    # activity_id may still be null for work_task costs — delete those first in real downgrade
    op.execute("DELETE FROM costs WHERE activity_id IS NULL")
    op.alter_column("costs", "activity_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.execute("DROP TYPE IF EXISTS work_task_status")
    op.execute("DROP TYPE IF EXISTS cost_source")
