from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import SoilLabVerificationStatus
from app.models.soil_lab import SoilLabAnalysis, SoilLabResult


class SoilLabAnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_activity(self, activity_id: UUID) -> list[SoilLabAnalysis]:
        stmt = (
            select(SoilLabAnalysis)
            .options(selectinload(SoilLabAnalysis.results))
            .where(SoilLabAnalysis.activity_id == activity_id)
            .order_by(SoilLabAnalysis.sampled_on, SoilLabAnalysis.created_at)
        )
        return list(self.db.scalars(stmt).unique().all())

    def list_for_parcel(self, parcel_id: UUID) -> list[SoilLabAnalysis]:
        stmt = (
            select(SoilLabAnalysis)
            .options(selectinload(SoilLabAnalysis.results))
            .where(SoilLabAnalysis.parcel_id == parcel_id)
            .order_by(SoilLabAnalysis.sampled_on.desc(), SoilLabAnalysis.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_latest_verified(self, parcel_id: UUID) -> SoilLabAnalysis | None:
        stmt = (
            select(SoilLabAnalysis)
            .options(selectinload(SoilLabAnalysis.results))
            .where(
                SoilLabAnalysis.parcel_id == parcel_id,
                SoilLabAnalysis.verification_status == SoilLabVerificationStatus.VERIFIED,
            )
            .order_by(SoilLabAnalysis.sampled_on.desc(), SoilLabAnalysis.created_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).unique().first()

    def get(self, analysis_id: UUID) -> SoilLabAnalysis | None:
        stmt = (
            select(SoilLabAnalysis)
            .options(selectinload(SoilLabAnalysis.results))
            .where(SoilLabAnalysis.id == analysis_id)
        )
        return self.db.scalars(stmt).unique().first()

    def add(self, analysis: SoilLabAnalysis) -> SoilLabAnalysis:
        self.db.add(analysis)
        return analysis

    def add_result(self, result: SoilLabResult) -> SoilLabResult:
        self.db.add(result)
        return result

    def get_result(self, result_id: UUID) -> SoilLabResult | None:
        return self.db.get(SoilLabResult, result_id)

    def delete(self, analysis: SoilLabAnalysis) -> None:
        self.db.delete(analysis)

    def delete_result(self, result: SoilLabResult) -> None:
        self.db.delete(result)
