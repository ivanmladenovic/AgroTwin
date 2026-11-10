"""Link disease cases and subsidies to journal activities

Revision ID: r7s8t9u0v1w2
Revises: q6r7s8t9u0v1
Create Date: 2026-10-08 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "r7s8t9u0v1w2"
down_revision: Union[str, Sequence[str], None] = "q6r7s8t9u0v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "disease_cases",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_disease_cases_activity_id", "disease_cases", ["activity_id"])
    op.create_foreign_key(
        "fk_disease_cases_activity_id",
        "disease_cases",
        "activities",
        ["activity_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "subsidies",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_subsidies_activity_id", "subsidies", ["activity_id"])
    op.create_foreign_key(
        "fk_subsidies_activity_id",
        "subsidies",
        "activities",
        ["activity_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_subsidies_activity_id", "subsidies", type_="foreignkey")
    op.drop_index("ix_subsidies_activity_id", table_name="subsidies")
    op.drop_column("subsidies", "activity_id")

    op.drop_constraint("fk_disease_cases_activity_id", "disease_cases", type_="foreignkey")
    op.drop_index("ix_disease_cases_activity_id", table_name="disease_cases")
    op.drop_column("disease_cases", "activity_id")
