from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.farm import Farm
from app.models.planning import PlanningPlan, PlanningPlanItem, PlanningSeason


class PlanningSeasonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[PlanningSeason]]:
        return (
            select(PlanningSeason)
            .options(
                selectinload(PlanningSeason.plans)
                .selectinload(PlanningPlan.items)
                .selectinload(PlanningPlanItem.expert_reviews)
            )
            .join(Farm, PlanningSeason.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )

    def list_for_parcel(self, owner_id: UUID, parcel_id: UUID) -> list[PlanningSeason]:
        stmt = (
            self._owned(owner_id)
            .where(PlanningSeason.parcel_id == parcel_id)
            .order_by(PlanningSeason.year.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_for_owner(self, season_id: UUID, owner_id: UUID) -> PlanningSeason | None:
        return self.db.scalars(self._owned(owner_id).where(PlanningSeason.id == season_id)).unique().first()

    def get_by_parcel_year(self, owner_id: UUID, parcel_id: UUID, year: int) -> PlanningSeason | None:
        stmt = self._owned(owner_id).where(
            PlanningSeason.parcel_id == parcel_id,
            PlanningSeason.year == year,
        )
        return self.db.scalars(stmt).unique().first()

    def add(self, season: PlanningSeason) -> PlanningSeason:
        self.db.add(season)
        return season


class PlanningPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[PlanningPlan]]:
        return (
            select(PlanningPlan)
            .options(
                selectinload(PlanningPlan.items).selectinload(PlanningPlanItem.expert_reviews),
                selectinload(PlanningPlan.season),
            )
            .join(PlanningSeason, PlanningPlan.planning_season_id == PlanningSeason.id)
            .join(Farm, PlanningSeason.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )

    def get_for_owner(self, plan_id: UUID, owner_id: UUID) -> PlanningPlan | None:
        return self.db.scalars(self._owned(owner_id).where(PlanningPlan.id == plan_id)).unique().first()

    def list_for_season(self, owner_id: UUID, season_id: UUID) -> list[PlanningPlan]:
        stmt = (
            self._owned(owner_id)
            .where(PlanningPlan.planning_season_id == season_id)
            .order_by(PlanningPlan.type, PlanningPlan.version.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def add(self, plan: PlanningPlan) -> PlanningPlan:
        self.db.add(plan)
        return plan


class PlanningPlanItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, item: PlanningPlanItem) -> PlanningPlanItem:
        self.db.add(item)
        return item
