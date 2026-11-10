"""Enterprise review record for existing parcel alerts

Revision ID: b1c2d3e4f6a7
Revises: a0b1c2d3e4f5
Create Date: 2026-10-20 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1c2d3e4f6a7"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_alert_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["enterprise_organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["parcel_alerts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organization_id", "alert_id", name="uq_enterprise_alert_review_org_alert"),
    )
    op.create_index(
        "ix_enterprise_alert_reviews_organization_id",
        "enterprise_alert_reviews",
        ["organization_id"],
    )
    op.create_index(
        "ix_enterprise_alert_reviews_alert_id",
        "enterprise_alert_reviews",
        ["alert_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_enterprise_alert_reviews_alert_id", table_name="enterprise_alert_reviews")
    op.drop_index("ix_enterprise_alert_reviews_organization_id", table_name="enterprise_alert_reviews")
    op.drop_table("enterprise_alert_reviews")
