from datetime import date
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.disease import DiseaseCase, DiseaseObservation
from app.models.enums import DiseaseCaseStatus, DiseaseCategory
from app.models.farm import Farm
from app.models.parcel import Parcel


class DiseaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[DiseaseCase]]:
        return (
            select(DiseaseCase)
            .join(Farm, DiseaseCase.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(selectinload(DiseaseCase.observations))
        )

    def list_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        row_id: UUID | None = None,
        tree_id: UUID | None = None,
        status: DiseaseCaseStatus | None = None,
        category: DiseaseCategory | None = None,
    ) -> list[DiseaseCase]:
        stmt = self._owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(DiseaseCase.parcel_id == parcel_id)
        if row_id is not None:
            stmt = stmt.where(DiseaseCase.row_id == row_id)
        if tree_id is not None:
            stmt = stmt.where(DiseaseCase.tree_id == tree_id)
        if status is not None:
            stmt = stmt.where(DiseaseCase.status == status)
        if category is not None:
            stmt = stmt.where(DiseaseCase.category == category)
        stmt = stmt.order_by(DiseaseCase.detected_on.desc(), DiseaseCase.created_at.desc())
        return list(self.db.scalars(stmt).unique().all())

    def list_for_tree(self, tree_id: UUID) -> list[DiseaseCase]:
        stmt = (
            select(DiseaseCase)
            .where(DiseaseCase.tree_id == tree_id)
            .options(selectinload(DiseaseCase.observations))
            .order_by(DiseaseCase.detected_on.desc(), DiseaseCase.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def list_open_for_tree(self, tree_id: UUID) -> list[DiseaseCase]:
        stmt = (
            select(DiseaseCase)
            .where(DiseaseCase.tree_id == tree_id, DiseaseCase.status != DiseaseCaseStatus.RESOLVED)
            .order_by(DiseaseCase.detected_on.desc())
        )
        return list(self.db.scalars(stmt).all())

    def severe_tree_ids(self, parcel_id: UUID) -> set[UUID]:
        from app.models.enums import DiseaseSeverity

        stmt = select(DiseaseCase.tree_id).where(
            DiseaseCase.parcel_id == parcel_id,
            DiseaseCase.tree_id.is_not(None),
            DiseaseCase.status != DiseaseCaseStatus.RESOLVED,
            DiseaseCase.severity.in_((DiseaseSeverity.HIGH, DiseaseSeverity.CRITICAL)),
        )
        return {tree_id for tree_id in self.db.scalars(stmt).all() if tree_id is not None}

    def get_for_owner(self, case_id: UUID, owner_id: UUID) -> DiseaseCase | None:
        stmt = self._owned(owner_id).where(DiseaseCase.id == case_id)
        return self.db.scalars(stmt).unique().first()

    def add(self, case: DiseaseCase) -> DiseaseCase:
        self.db.add(case)
        return case


class ObservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_case(self, case_id: UUID) -> list[DiseaseObservation]:
        stmt = (
            select(DiseaseObservation)
            .where(DiseaseObservation.disease_case_id == case_id)
            .order_by(DiseaseObservation.observed_on.desc(), DiseaseObservation.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get(self, observation_id: UUID) -> DiseaseObservation | None:
        return self.db.get(DiseaseObservation, observation_id)

    def add(self, observation: DiseaseObservation) -> DiseaseObservation:
        self.db.add(observation)
        return observation
