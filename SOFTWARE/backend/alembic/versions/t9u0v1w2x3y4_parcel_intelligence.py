"""parcel intelligence events, alerts, analysis runs, notifications

Revision ID: t9u0v1w2x3y4
Revises: s8t9u0v1w2x3
Create Date: 2026-10-08 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "t9u0v1w2x3y4"
down_revision: Union[str, Sequence[str], None] = "s8t9u0v1w2x3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    event_kind = postgresql.ENUM(
        "satellite_observation",
        "satellite_anomaly",
        "weather_event",
        "activity_protection",
        "activity_fertilization",
        "activity_irrigation",
        "harvest_recorded",
        "yield_deviation",
        "manual_request",
        "scheduled",
        name="parcel_analysis_event_kind",
        create_type=False,
    )
    run_status = postgresql.ENUM(
        "skipped",
        "completed",
        "failed",
        name="parcel_analysis_run_status",
        create_type=False,
    )
    alert_severity = postgresql.ENUM(
        "INFO",
        "WARNING",
        "CRITICAL",
        name="parcel_alert_severity",
        create_type=False,
    )
    alert_status = postgresql.ENUM(
        "open",
        "acknowledged",
        "resolved",
        name="parcel_alert_status",
        create_type=False,
    )
    postgresql.ENUM(
        "satellite_observation",
        "satellite_anomaly",
        "weather_event",
        "activity_protection",
        "activity_fertilization",
        "activity_irrigation",
        "harvest_recorded",
        "yield_deviation",
        "manual_request",
        "scheduled",
        name="parcel_analysis_event_kind",
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "skipped",
        "completed",
        "failed",
        name="parcel_analysis_run_status",
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "INFO",
        "WARNING",
        "CRITICAL",
        name="parcel_alert_severity",
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "open",
        "acknowledged",
        "resolved",
        name="parcel_alert_status",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "parcel_analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("trigger_kinds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("skip_reason", sa.String(length=128), nullable=True),
        sa.Column("ai_called", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validated_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parcel_analysis_runs_parcel_id", "parcel_analysis_runs", ["parcel_id"])
    op.create_index("ix_parcel_analysis_runs_status", "parcel_analysis_runs", ["status"])

    op.create_table(
        "parcel_analysis_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", event_kind, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["parcel_analysis_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parcel_analysis_events_parcel_id", "parcel_analysis_events", ["parcel_id"])
    op.create_index("ix_parcel_analysis_events_kind", "parcel_analysis_events", ["kind"])
    op.create_index("ix_parcel_analysis_events_analysis_run_id", "parcel_analysis_events", ["analysis_run_id"])

    op.create_table(
        "parcel_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column("status", alert_status, nullable=False),
        sa.Column("issue_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("observed_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("possible_causes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_events", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["parcel_analysis_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parcel_alerts_parcel_id", "parcel_alerts", ["parcel_id"])
    op.create_index("ix_parcel_alerts_severity", "parcel_alerts", ["severity"])
    op.create_index("ix_parcel_alerts_status", "parcel_alerts", ["status"])
    op.create_index("ix_parcel_alerts_issue_key", "parcel_alerts", ["issue_key"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_parcel_alerts_open_issue
        ON parcel_alerts (parcel_id, issue_key)
        WHERE status IN ('open', 'acknowledged')
        """
    )

    op.create_table(
        "user_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alert_id"], ["parcel_alerts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_notifications_user_id", "user_notifications", ["user_id"])
    op.create_index("ix_user_notifications_parcel_id", "user_notifications", ["parcel_id"])
    op.create_index("ix_user_notifications_alert_id", "user_notifications", ["alert_id"])


def downgrade() -> None:
    op.drop_index("ix_user_notifications_alert_id", table_name="user_notifications")
    op.drop_index("ix_user_notifications_parcel_id", table_name="user_notifications")
    op.drop_index("ix_user_notifications_user_id", table_name="user_notifications")
    op.drop_table("user_notifications")
    op.execute("DROP INDEX IF EXISTS uq_parcel_alerts_open_issue")
    op.drop_index("ix_parcel_alerts_issue_key", table_name="parcel_alerts")
    op.drop_index("ix_parcel_alerts_status", table_name="parcel_alerts")
    op.drop_index("ix_parcel_alerts_severity", table_name="parcel_alerts")
    op.drop_index("ix_parcel_alerts_parcel_id", table_name="parcel_alerts")
    op.drop_table("parcel_alerts")
    op.drop_index("ix_parcel_analysis_events_analysis_run_id", table_name="parcel_analysis_events")
    op.drop_index("ix_parcel_analysis_events_kind", table_name="parcel_analysis_events")
    op.drop_index("ix_parcel_analysis_events_parcel_id", table_name="parcel_analysis_events")
    op.drop_table("parcel_analysis_events")
    op.drop_index("ix_parcel_analysis_runs_status", table_name="parcel_analysis_runs")
    op.drop_index("ix_parcel_analysis_runs_parcel_id", table_name="parcel_analysis_runs")
    op.drop_table("parcel_analysis_runs")
    op.execute("DROP TYPE IF EXISTS parcel_alert_status")
    op.execute("DROP TYPE IF EXISTS parcel_alert_severity")
    op.execute("DROP TYPE IF EXISTS parcel_analysis_run_status")
    op.execute("DROP TYPE IF EXISTS parcel_analysis_event_kind")
