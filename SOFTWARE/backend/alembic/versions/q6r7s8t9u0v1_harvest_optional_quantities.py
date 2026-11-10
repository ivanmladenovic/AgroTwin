"""allow draft harvests without quantities

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-10-08 08:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "q6r7s8t9u0v1"
down_revision: Union[str, Sequence[str], None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_harvest_events_loss_lte_gross", "harvest_events", type_="check")
    op.drop_constraint("ck_harvest_events_gross_positive", "harvest_events", type_="check")
    op.drop_column("harvest_events", "net_quantity")
    op.alter_column(
        "harvest_events",
        "gross_quantity",
        existing_type=sa.Numeric(precision=12, scale=3),
        nullable=True,
    )
    op.add_column(
        "harvest_events",
        sa.Column(
            "net_quantity",
            sa.Numeric(precision=12, scale=3),
            sa.Computed(
                "CASE WHEN gross_quantity IS NULL THEN NULL ELSE gross_quantity - loss_quantity END",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_harvest_events_gross_positive",
        "harvest_events",
        "gross_quantity IS NULL OR gross_quantity > 0",
    )
    op.create_check_constraint(
        "ck_harvest_events_loss_lte_gross",
        "harvest_events",
        "gross_quantity IS NULL OR loss_quantity <= gross_quantity",
    )


def downgrade() -> None:
    op.drop_constraint("ck_harvest_events_loss_lte_gross", "harvest_events", type_="check")
    op.drop_constraint("ck_harvest_events_gross_positive", "harvest_events", type_="check")
    op.execute("DELETE FROM harvest_events WHERE gross_quantity IS NULL")
    op.drop_column("harvest_events", "net_quantity")
    op.alter_column(
        "harvest_events",
        "gross_quantity",
        existing_type=sa.Numeric(precision=12, scale=3),
        nullable=False,
    )
    op.add_column(
        "harvest_events",
        sa.Column(
            "net_quantity",
            sa.Numeric(precision=12, scale=3),
            sa.Computed("gross_quantity - loss_quantity", persisted=True),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_harvest_events_gross_positive",
        "harvest_events",
        "gross_quantity > 0",
    )
    op.create_check_constraint(
        "ck_harvest_events_loss_lte_gross",
        "harvest_events",
        "loss_quantity <= gross_quantity",
    )
