from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ParcelAlertRead(BaseModel):
    id: UUID
    parcel_id: UUID
    severity: str
    status: str
    issue_key: str
    title: str
    summary: str
    observed_facts: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    source_events: list[str] = Field(default_factory=list)
    confidence: Decimal | None = None
    evidence: dict = Field(default_factory=dict)
    created_at: datetime
    resolved_at: datetime | None = None


class ParcelAnalysisRunRead(BaseModel):
    id: UUID
    parcel_id: UUID
    status: str
    ai_called: bool
    skip_reason: str | None = None
    trigger_kinds: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    validated_result: dict | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class IntelligenceDashboardRead(BaseModel):
    parcel_id: UUID
    parcel_name: str | None = None
    available: bool
    active_alerts: list[ParcelAlertRead] = Field(default_factory=list)
    resolved_alerts: list[ParcelAlertRead] = Field(default_factory=list)
    last_analysis: ParcelAnalysisRunRead | None = None
    next_scheduled_at: datetime | None = None
    disclaimer: str
    read_only: bool = False


class UserNotificationRead(BaseModel):
    id: UUID
    parcel_id: UUID | None = None
    alert_id: UUID | None = None
    severity: str
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime
    payload: dict = Field(default_factory=dict)
