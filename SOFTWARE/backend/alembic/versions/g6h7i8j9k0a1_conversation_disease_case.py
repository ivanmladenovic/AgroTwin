"""link agronomist conversations to disease cases

Revision ID: g6h7i8j9k0a1
Revises: f5a6b7c8d9e0
Create Date: 2026-09-20 14:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "g6h7i8j9k0a1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_conversations",
        sa.Column("disease_case_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_ai_conversations_disease_case_id"), "ai_conversations", ["disease_case_id"], unique=False)
    op.create_foreign_key(
        "fk_ai_conversations_disease_case_id",
        "ai_conversations",
        "disease_cases",
        ["disease_case_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_conversations_disease_case_id", "ai_conversations", type_="foreignkey")
    op.drop_index(op.f("ix_ai_conversations_disease_case_id"), table_name="ai_conversations")
    op.drop_column("ai_conversations", "disease_case_id")
