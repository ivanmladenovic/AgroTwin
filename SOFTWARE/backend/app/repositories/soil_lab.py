from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.soil_lab import SoilLabAnalysis


class SoilLabAnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_activity(self, activity_id: UUID) -> list[SoilLabAnalysis]:
        stmt = (
            select(SoilLabAnalysis)
            .where(SoilLabAnalysis.activity_id == activity_id)
            .order_by(SoilLabAnalysis.sampled_on, SoilLabAnalysis.created_at)
        )
        return list(self.db.scalars(stmt).all())

    def list_for_parcel(self, parcel_id: UUID) -> list[SoilLabAnalysis]:
        stmt = (
            select(SoilLabAnalysis)
            .where(SoilLabAnalysis.parcel_id == parcel_id)
            .order_by(SoilLabAnalysis.sampled_on.desc(), SoilLabAnalysis.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get(self, analysis_id: UUID) -> SoilLabAnalysis | None:
        return self.db.get(SoilLabAnalysis, analysis_id)

    def add(self, analysis: SoilLabAnalysis) -> SoilLabAnalysis:
        self.db.add(analysis)
        return analysis

    def delete(self, analysis: SoilLabAnalysis) -> None:
        self.db.delete(analysis)
