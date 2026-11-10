"""soil lab structured results and verification

Revision ID: l1m2n3o4p5q6
Revises: k0a1b2c3d4e5
Create Date: 2026-10-06 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, Sequence[str], None] = "k0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    extraction_status = postgresql.ENUM(
        "pending",
        "running",
        "succeeded",
        "failed",
        name="soil_lab_extraction_status",
    )
    verification_status = postgresql.ENUM(
        "extracted",
        "needs_review",
        "verified",
        "skipped",
        name="soil_lab_verification_status",
    )
    bind = op.get_bind()
    extraction_status.create(bind, checkfirst=True)
    verification_status.create(bind, checkfirst=True)

    op.add_column("soil_lab_analyses", sa.Column("analysis_date", sa.Date(), nullable=True))
    op.add_column("soil_lab_analyses", sa.Column("laboratory_name", sa.String(length=255), nullable=True))
    op.add_column(
        "soil_lab_analyses",
        sa.Column("sample_depth_from_cm", sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.add_column(
        "soil_lab_analyses",
        sa.Column("sample_depth_to_cm", sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.add_column(
        "soil_lab_analyses",
        sa.Column(
            "extraction_status",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                name="soil_lab_extraction_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "soil_lab_analyses",
        sa.Column(
            "verification_status",
            postgresql.ENUM(
                "extracted",
                "needs_review",
                "verified",
                "skipped",
                name="soil_lab_verification_status",
                create_type=False,
            ),
            nullable=False,
            server_default="needs_review",
        ),
    )
    op.add_column("soil_lab_analyses", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.add_column("soil_lab_analyses", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_soil_lab_analyses_verification_status"),
        "soil_lab_analyses",
        ["verification_status"],
        unique=False,
    )

    op.create_table(
        "soil_lab_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parameter_code", sa.String(length=64), nullable=False),
        sa.Column("original_parameter_name", sa.String(length=512), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=128), nullable=True),
        sa.Column("depth_from_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("depth_to_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "verification_status",
            postgresql.ENUM(
                "extracted",
                "needs_review",
                "verified",
                "skipped",
                name="soil_lab_verification_status",
                create_type=False,
            ),
            nullable=False,
            server_default="extracted",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["soil_lab_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_soil_lab_results_analysis_id"), "soil_lab_results", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_soil_lab_results_parameter_code"), "soil_lab_results", ["parameter_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_soil_lab_results_parameter_code"), table_name="soil_lab_results")
    op.drop_index(op.f("ix_soil_lab_results_analysis_id"), table_name="soil_lab_results")
    op.drop_table("soil_lab_results")
    op.drop_index(op.f("ix_soil_lab_analyses_verification_status"), table_name="soil_lab_analyses")
    op.drop_column("soil_lab_analyses", "extracted_text")
    op.drop_column("soil_lab_analyses", "extraction_error")
    op.drop_column("soil_lab_analyses", "verification_status")
    op.drop_column("soil_lab_analyses", "extraction_status")
    op.drop_column("soil_lab_analyses", "sample_depth_to_cm")
    op.drop_column("soil_lab_analyses", "sample_depth_from_cm")
    op.drop_column("soil_lab_analyses", "laboratory_name")
    op.drop_column("soil_lab_analyses", "analysis_date")
    op.execute("DROP TYPE IF EXISTS soil_lab_verification_status")
    op.execute("DROP TYPE IF EXISTS soil_lab_extraction_status")
