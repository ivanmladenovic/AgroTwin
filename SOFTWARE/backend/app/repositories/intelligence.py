from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ParcelAlertStatus, ParcelAnalysisRunStatus
from app.models.farm import Farm
from app.models.intelligence import (
    ParcelAlert,
    ParcelAnalysisEvent,
    ParcelAnalysisRun,
    UserNotification,
)
from app.models.parcel import Parcel


class IntelligenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_event(self, event: ParcelAnalysisEvent) -> ParcelAnalysisEvent:
        self.db.add(event)
        return event

    def pending_events(self, parcel_id: UUID | None = None, *, limit: int = 200) -> list[ParcelAnalysisEvent]:
        stmt = (
            select(ParcelAnalysisEvent)
            .where(ParcelAnalysisEvent.processed_at.is_(None))
            .order_by(ParcelAnalysisEvent.created_at.asc())
            .limit(limit)
        )
        if parcel_id is not None:
            stmt = stmt.where(ParcelAnalysisEvent.parcel_id == parcel_id)
        return list(self.db.scalars(stmt).all())

    def add_run(self, run: ParcelAnalysisRun) -> ParcelAnalysisRun:
        self.db.add(run)
        return run

    def latest_run(self, parcel_id: UUID) -> ParcelAnalysisRun | None:
        return self.db.scalars(
            select(ParcelAnalysisRun)
            .where(ParcelAnalysisRun.parcel_id == parcel_id)
            .order_by(ParcelAnalysisRun.started_at.desc())
            .limit(1)
        ).first()

    def latest_ai_run(self, parcel_id: UUID) -> ParcelAnalysisRun | None:
        return self.db.scalars(
            select(ParcelAnalysisRun)
            .where(
                ParcelAnalysisRun.parcel_id == parcel_id,
                ParcelAnalysisRun.ai_called.is_(True),
                ParcelAnalysisRun.status == ParcelAnalysisRunStatus.COMPLETED,
            )
            .order_by(ParcelAnalysisRun.started_at.desc())
            .limit(1)
        ).first()

    def open_alerts(self, parcel_id: UUID) -> list[ParcelAlert]:
        return list(
            self.db.scalars(
                select(ParcelAlert)
                .where(
                    ParcelAlert.parcel_id == parcel_id,
                    ParcelAlert.status.in_(
                        [ParcelAlertStatus.OPEN, ParcelAlertStatus.ACKNOWLEDGED]
                    ),
                )
                .order_by(ParcelAlert.created_at.desc())
            ).all()
        )

    def resolved_alerts(self, parcel_id: UUID, *, limit: int = 20) -> list[ParcelAlert]:
        return list(
            self.db.scalars(
                select(ParcelAlert)
                .where(
                    ParcelAlert.parcel_id == parcel_id,
                    ParcelAlert.status == ParcelAlertStatus.RESOLVED,
                )
                .order_by(ParcelAlert.resolved_at.desc().nullslast(), ParcelAlert.created_at.desc())
                .limit(limit)
            ).all()
        )

    def find_open_alert(self, parcel_id: UUID, issue_key: str) -> ParcelAlert | None:
        return self.db.scalars(
            select(ParcelAlert).where(
                ParcelAlert.parcel_id == parcel_id,
                ParcelAlert.issue_key == issue_key,
                ParcelAlert.status.in_(
                    [ParcelAlertStatus.OPEN, ParcelAlertStatus.ACKNOWLEDGED]
                ),
            )
        ).first()

    def add_alert(self, alert: ParcelAlert) -> ParcelAlert:
        self.db.add(alert)
        return alert

    def add_notification(self, notification: UserNotification) -> UserNotification:
        self.db.add(notification)
        return notification

    def list_notifications(self, user_id: UUID, *, limit: int = 50) -> list[UserNotification]:
        return list(
            self.db.scalars(
                select(UserNotification)
                .where(UserNotification.user_id == user_id)
                .order_by(UserNotification.created_at.desc())
                .limit(limit)
            ).all()
        )

    def get_alert_for_owner(self, alert_id: UUID, owner_id: UUID) -> ParcelAlert | None:
        return self.db.scalars(
            select(ParcelAlert)
            .join(Parcel, ParcelAlert.parcel_id == Parcel.id)
            .join(Farm, Parcel.farm_id == Farm.id)
            .where(ParcelAlert.id == alert_id, Farm.owner_id == owner_id)
        ).first()

    def parcels_for_scheduled(self) -> list[Parcel]:
        return list(self.db.scalars(select(Parcel).order_by(Parcel.name)).all())

    def mark_events_processed(
        self,
        events: list[ParcelAnalysisEvent],
        *,
        run_id: UUID,
        processed_at: datetime,
    ) -> None:
        for event in events:
            event.processed_at = processed_at
            event.analysis_run_id = run_id
