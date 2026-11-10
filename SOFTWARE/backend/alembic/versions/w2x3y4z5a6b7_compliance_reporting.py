"""compliance report definitions and audit runs

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-10-08 16:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "w2x3y4z5a6b7"
down_revision: Union[str, Sequence[str], None] = "v1w2x3y4z5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REPORT_TYPES = (
    "farm_profile",
    "parcel_register",
    "plant_protection",
    "fertilization_inputs",
    "harvest_traceability",
    "farm_activity",
    "irrigation_water",
    "compliance_package",
)
REPORT_FORMATS = ("json", "csv", "pdf", "zip")


def upgrade() -> None:
    report_type = postgresql.ENUM(*REPORT_TYPES, name="compliance_report_type", create_type=False)
    report_format = postgresql.ENUM(*REPORT_FORMATS, name="compliance_report_format", create_type=False)
    postgresql.ENUM(*REPORT_TYPES, name="compliance_report_type").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(*REPORT_FORMATS, name="compliance_report_format").create(op.get_bind(), checkfirst=True)

    op.create_table(
        "compliance_report_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("type", report_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(length=128), nullable=False),
        sa.Column("template", sa.String(length=128), nullable=False, server_default="tabular_v1"),
        sa.Column("version", sa.String(length=16), nullable=False, server_default="1.0"),
        sa.Column("default_filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("include_in_default_package", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "version", name="uq_compliance_report_def_type_version"),
    )
    op.create_index("ix_compliance_report_definitions_type", "compliance_report_definitions", ["type"])

    op.create_table(
        "compliance_report_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", report_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("format", report_format, nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("parcel_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("definition_version", sa.String(length=16), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("generated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["definition_id"], ["compliance_report_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_report_runs_farm_id", "compliance_report_runs", ["farm_id"])
    op.create_index("ix_compliance_report_runs_report_type", "compliance_report_runs", ["report_type"])
    op.create_index("ix_compliance_report_runs_generated_by_id", "compliance_report_runs", ["generated_by_id"])


def downgrade() -> None:
    op.drop_index("ix_compliance_report_runs_generated_by_id", table_name="compliance_report_runs")
    op.drop_index("ix_compliance_report_runs_report_type", table_name="compliance_report_runs")
    op.drop_index("ix_compliance_report_runs_farm_id", table_name="compliance_report_runs")
    op.drop_table("compliance_report_runs")
    op.drop_index("ix_compliance_report_definitions_type", table_name="compliance_report_definitions")
    op.drop_table("compliance_report_definitions")
    op.execute("DROP TYPE IF EXISTS compliance_report_format")
    op.execute("DROP TYPE IF EXISTS compliance_report_type")
