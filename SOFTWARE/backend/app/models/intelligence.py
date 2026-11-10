from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ParcelAlertSeverity,
    ParcelAlertStatus,
    ParcelAnalysisEventKind,
    ParcelAnalysisRunStatus,
    pg_enum,
)

if TYPE_CHECKING:
    pass


class ParcelAnalysisEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Internal queue of analysis triggers (not exposed as product notifications)."""

    __tablename__ = "parcel_analysis_events"

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ParcelAnalysisEventKind] = mapped_column(
        pg_enum(ParcelAnalysisEventKind, "parcel_analysis_event_kind"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcel_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class ParcelAnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parcel_analysis_runs"

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ParcelAnalysisRunStatus] = mapped_column(
        pg_enum(ParcelAnalysisRunStatus, "parcel_analysis_run_status"),
        nullable=False,
        index=True,
    )
    trigger_kinds: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    change_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_called: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validated_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ParcelAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parcel_alerts"

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[ParcelAlertSeverity] = mapped_column(
        pg_enum(ParcelAlertSeverity, "parcel_alert_severity"),
        nullable=False,
        index=True,
    )
    status: Mapped[ParcelAlertStatus] = mapped_column(
        pg_enum(ParcelAlertStatus, "parcel_alert_status"),
        nullable=False,
        default=ParcelAlertStatus.OPEN,
        index=True,
    )
    issue_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    observed_facts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    possible_causes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recommended_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcel_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """In-app notifications (greenfield — no prior notification subsystem existed)."""

    __tablename__ = "user_notifications"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    alert_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcel_alerts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
