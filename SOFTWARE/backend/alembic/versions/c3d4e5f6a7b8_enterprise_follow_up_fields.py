"""Assignee, due date and alert link on enterprise follow-ups

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f6a7
Create Date: 2026-10-20 12:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_follow_ups",
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("enterprise_follow_ups", sa.Column("due_on", sa.Date(), nullable=True))
    op.add_column(
        "enterprise_follow_ups",
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_enterprise_follow_ups_assignee_user_id",
        "enterprise_follow_ups",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_enterprise_follow_ups_alert_id",
        "enterprise_follow_ups",
        "parcel_alerts",
        ["alert_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_enterprise_follow_ups_assignee_user_id",
        "enterprise_follow_ups",
        ["assignee_user_id"],
    )
    op.create_index("ix_enterprise_follow_ups_due_on", "enterprise_follow_ups", ["due_on"])
    op.create_index("ix_enterprise_follow_ups_alert_id", "enterprise_follow_ups", ["alert_id"])


def downgrade() -> None:
    op.drop_index("ix_enterprise_follow_ups_alert_id", table_name="enterprise_follow_ups")
    op.drop_index("ix_enterprise_follow_ups_due_on", table_name="enterprise_follow_ups")
    op.drop_index("ix_enterprise_follow_ups_assignee_user_id", table_name="enterprise_follow_ups")
    op.drop_constraint(
        "fk_enterprise_follow_ups_alert_id", "enterprise_follow_ups", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_enterprise_follow_ups_assignee_user_id", "enterprise_follow_ups", type_="foreignkey"
    )
    op.drop_column("enterprise_follow_ups", "alert_id")
    op.drop_column("enterprise_follow_ups", "due_on")
    op.drop_column("enterprise_follow_ups", "assignee_user_id")
