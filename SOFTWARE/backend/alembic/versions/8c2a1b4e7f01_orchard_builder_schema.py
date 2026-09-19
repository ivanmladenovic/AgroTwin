"""orchard builder schema

Revision ID: 8c2a1b4e7f01
Revises: 475044acf976
Create Date: 2026-09-14 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8c2a1b4e7f01"
down_revision: Union[str, Sequence[str], None] = "475044acf976"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE health_status ADD VALUE IF NOT EXISTS 'monitoring'")
        op.execute("ALTER TYPE health_status ADD VALUE IF NOT EXISTS 'issue'")

    op.execute("UPDATE trees SET health_status = 'monitoring' WHERE health_status = 'watch'")
    op.execute("UPDATE trees SET health_status = 'issue' WHERE health_status = 'diseased'")
    op.execute("UPDATE trees SET status = 'removed' WHERE status IN ('missing', 'dead')")

    well_location = postgresql.ENUM(
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
        name="well_location",
    )
    well_location.create(op.get_bind(), checkfirst=True)

    op.add_column("parcels", sa.Column("row_count", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("trees_per_row", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("row_spacing_m", sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column("parcels", sa.Column("tree_spacing_m", sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column("parcels", sa.Column("default_variety", sa.String(length=128), nullable=True))
    op.add_column("parcels", sa.Column("default_planting_year", sa.Integer(), nullable=True))
    op.add_column(
        "parcels",
        sa.Column("starting_tree_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("parcels", sa.Column("well_location", well_location, nullable=True))
    op.add_column("parcels", sa.Column("well_x", sa.Numeric(precision=12, scale=4), nullable=True))
    op.add_column("parcels", sa.Column("well_y", sa.Numeric(precision=12, scale=4), nullable=True))
    op.add_column(
        "parcels",
        sa.Column("orientation_degrees", sa.Numeric(precision=6, scale=2), server_default="0", nullable=False),
    )

    op.add_column(
        "orchard_rows",
        sa.Column("tree_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.alter_column("orchard_rows", "number", new_column_name="row_number")

    op.alter_column("trees", "code", new_column_name="public_id")
    op.add_column(
        "trees",
        sa.Column("normalized_x", sa.Numeric(precision=12, scale=4), server_default="0", nullable=False),
    )
    op.add_column(
        "trees",
        sa.Column("normalized_y", sa.Numeric(precision=12, scale=4), server_default="0", nullable=False),
    )
    op.execute(
        "ALTER TABLE trees RENAME CONSTRAINT uq_trees_parcel_code TO uq_trees_parcel_public_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE trees RENAME CONSTRAINT uq_trees_parcel_public_id TO uq_trees_parcel_code"
    )
    op.drop_column("trees", "normalized_y")
    op.drop_column("trees", "normalized_x")
    op.alter_column("trees", "public_id", new_column_name="code")
    op.alter_column("orchard_rows", "row_number", new_column_name="number")
    op.drop_column("orchard_rows", "tree_count")
    op.drop_column("parcels", "orientation_degrees")
    op.drop_column("parcels", "well_y")
    op.drop_column("parcels", "well_x")
    op.drop_column("parcels", "well_location")
    op.drop_column("parcels", "starting_tree_number")
    op.drop_column("parcels", "default_planting_year")
    op.drop_column("parcels", "default_variety")
    op.drop_column("parcels", "tree_spacing_m")
    op.drop_column("parcels", "row_spacing_m")
    op.drop_column("parcels", "trees_per_row")
    op.drop_column("parcels", "row_count")
    postgresql.ENUM(name="well_location").drop(op.get_bind(), checkfirst=True)
