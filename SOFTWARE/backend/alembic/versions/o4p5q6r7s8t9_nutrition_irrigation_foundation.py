"""nutrition/irrigation plan kinds + parcel irrigation profile

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-10-06 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "o4p5q6r7s8t9"
down_revision: Union[str, Sequence[str], None] = "n3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_KINDS = (
    "soil_review",
    "nutrition_monitoring",
    "fertilization_window",
    "irrigation_monitoring",
    "irrigation_window",
    "estimated_need",
    "system_calculation",
)


def upgrade() -> None:
    for value in _NEW_KINDS:
        op.execute(f"ALTER TYPE planning_item_kind ADD VALUE IF NOT EXISTS '{value}'")

    irrigation_type = postgresql.ENUM(
        "drip",
        "sprinkler",
        "microsprinkler",
        "other",
        name="irrigation_type",
    )
    irrigation_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "parcels",
        sa.Column("has_irrigation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "parcels",
        sa.Column(
            "irrigation_type",
            postgresql.ENUM(
                "drip",
                "sprinkler",
                "microsprinkler",
                "other",
                name="irrigation_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("parcels", sa.Column("water_source", sa.String(length=128), nullable=True))
    op.add_column("parcels", sa.Column("emitter_flow_lph", sa.Numeric(8, 2), nullable=True))
    op.add_column("parcels", sa.Column("emitter_spacing_m", sa.Numeric(8, 2), nullable=True))
    op.add_column("parcels", sa.Column("line_count", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("irrigation_sections", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("irrigation_pressure_bar", sa.Numeric(8, 2), nullable=True))
    op.add_column("parcels", sa.Column("irrigation_efficiency", sa.Numeric(5, 2), nullable=True))
    op.add_column("parcels", sa.Column("irrigation_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("parcels", "irrigation_notes")
    op.drop_column("parcels", "irrigation_efficiency")
    op.drop_column("parcels", "irrigation_pressure_bar")
    op.drop_column("parcels", "irrigation_sections")
    op.drop_column("parcels", "line_count")
    op.drop_column("parcels", "emitter_spacing_m")
    op.drop_column("parcels", "emitter_flow_lph")
    op.drop_column("parcels", "water_source")
    op.drop_column("parcels", "irrigation_type")
    op.drop_column("parcels", "has_irrigation")
    postgresql.ENUM(name="irrigation_type").drop(op.get_bind(), checkfirst=True)
    # Enum values for planning_item_kind are left in place (Postgres cannot easily remove them).
