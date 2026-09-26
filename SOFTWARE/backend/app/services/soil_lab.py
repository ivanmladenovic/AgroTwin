from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.soil_lab import SoilLabAnalysis
from app.repositories.activity import ActivityRepository
from app.repositories.soil_lab import SoilLabAnalysisRepository
from app.repositories.tree import TreeRepository
from app.schemas.soil_lab import SoilLabAnalysisRead
from app.storage import get_storage

MAX_FILE_BYTES = 15 * 1024 * 1024
PDF_TYPES = {"application/pdf", "application/x-pdf"}


class SoilLabAnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = ActivityRepository(db)
        self.analyses = SoilLabAnalysisRepository(db)
        self.trees = TreeRepository(db)
        self.storage = get_storage()

    def list_for_activity(self, activity_id: UUID, owner_id: UUID) -> list[SoilLabAnalysisRead]:
        activity = self._activity(activity_id, owner_id)
        return [self.to_read(item) for item in self.analyses.list_for_activity(activity.id)]

    def get_analysis(self, analysis_id: UUID, owner_id: UUID) -> SoilLabAnalysis:
        analysis = self.analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError("Analiza zemljišta nije pronađena")
        self._activity(analysis.activity_id, owner_id)
        return analysis

    def create(
        self,
        activity_id: UUID,
        owner_id: UUID,
        *,
        tree_id: UUID,
        sampled_on: date,
        filename: str,
        content_type: str,
        content: bytes,
        created_by_id: UUID,
    ) -> SoilLabAnalysis:
        activity = self._activity(activity_id, owner_id)
        if activity.parcel_id is None:
            raise AppError("Analiza zemljišta zahteva parcelu", status_code=422, code="missing_parcel")
        if activity.activity_type.slug != "soil_analysis":
            raise AppError("Uzorke analize dodajete na aktivnost analize zemljišta", status_code=422, code="wrong_activity_type")
        if not content:
            raise AppError("Datoteka je prazna", status_code=422, code="empty_file")
        if len(content) > MAX_FILE_BYTES:
            raise AppError("Datoteka je veća od 15 MB", status_code=422, code="file_too_large")
        if not _is_pdf(filename, content_type):
            raise AppError("Prihvata se samo PDF analiza", status_code=422, code="invalid_file")
        tree_row = self.trees.get_for_parcel(activity.parcel_id, tree_id)
        if tree_row is None:
            raise AppError("Izabrana sadnica ne pripada parceli", status_code=422, code="invalid_tree")
        key = f"soil-lab/{activity.farm_id}/{activity.id}/{uuid4().hex}.pdf"
        self.storage.put(key, content, "application/pdf")
        analysis = SoilLabAnalysis(
            activity_id=activity.id,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            tree_id=tree_id,
            sampled_on=sampled_on,
            storage_key=key,
            original_filename=filename,
            content_type="application/pdf",
            size_bytes=len(content),
            created_by_id=created_by_id,
        )
        self.analyses.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def file_local_path(self, analysis: SoilLabAnalysis) -> Path | None:
        return self.storage.local_path(analysis.storage_key)

    def file_bytes(self, analysis: SoilLabAnalysis) -> tuple[bytes, str]:
        return self.storage.get(analysis.storage_key), analysis.content_type

    def to_read(self, analysis: SoilLabAnalysis) -> SoilLabAnalysisRead:
        tree_row = self.trees.get_for_parcel(analysis.parcel_id, analysis.tree_id)
        tree = tree_row[0] if tree_row else None
        row_number = tree_row[1] if tree_row else None
        return SoilLabAnalysisRead(
            id=analysis.id,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
            activity_id=analysis.activity_id,
            parcel_id=analysis.parcel_id,
            tree_id=analysis.tree_id,
            tree_public_id=tree.public_id if tree else None,
            row_id=tree.row_id if tree else None,
            row_number=row_number,
            sampled_on=analysis.sampled_on,
            original_filename=analysis.original_filename,
            content_type=analysis.content_type,
            size_bytes=analysis.size_bytes,
        )

    def _activity(self, activity_id: UUID, owner_id: UUID):
        activity = self.activities.get_for_owner(activity_id, owner_id)
        if activity is None:
            raise NotFoundError("Aktivnost nije pronađena")
        return activity


def _is_pdf(filename: str, content_type: str) -> bool:
    if (content_type or "").lower() in PDF_TYPES:
        return True
    return Path(filename).suffix.lower() == ".pdf"
