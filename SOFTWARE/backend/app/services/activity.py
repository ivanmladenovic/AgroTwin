from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.activity import Activity
from app.models.cost import Cost
from app.models.enums import (
    ActivitySemanticType,
    ActivityStatus,
    AttachmentEntityType,
    CostSource,
    ObservationCategory,
    ObservationStatus,
    ScopeType,
)
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.disease import DiseaseCase
from app.models.harvest import HarvestEvent
from app.models.planning import PlanningPlanItem
from app.models.subsidy import Subsidy
from app.repositories.activity import ActivityRepository
from app.repositories.catalog import CatalogRepository
from app.repositories.cost import CostRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.harvest import HarvestRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.photo import PhotoRepository
from app.repositories.row import RowRepository
from app.repositories.subsidy import SubsidyRepository
from app.repositories.tree import TreeRepository
from app.schemas.activity import (
    ActivityCreate,
    ActivityDiseaseSnippet,
    ActivityHarvestSnippet,
    ActivityLineItem,
    ActivityPlanItemSnippet,
    ActivityRead,
    ActivitySubsidySnippet,
    ActivityUpdate,
)
from app.schemas.catalog import CatalogItemRead
from app.schemas.cost import (
    CostCreate,
    CostItemRead,
    CostStandaloneCreate,
    CostSummaryRead,
    NamedAmount,
    QuantityLineRead,
    YearAmount,
)
from app.schemas.soil_lab import SoilLabAnalysisRead
from app.services.soil_lab import SoilLabAnalysisService
from app.services.subsidy import _percent

_SLUG_TO_SEMANTIC: dict[str, ActivitySemanticType] = {
    "irrigation": ActivitySemanticType.IRRIGATION,
    "fertilization": ActivitySemanticType.FERTILIZATION,
    "pruning": ActivitySemanticType.PRUNING,
    "planting": ActivitySemanticType.PLANTING,
    "spraying": ActivitySemanticType.TREATMENT,
    "disease_treatment": ActivitySemanticType.TREATMENT,
    "inspection": ActivitySemanticType.MONITORING,
    "observation": ActivitySemanticType.OBSERVATION,
    "harvesting": ActivitySemanticType.OTHER,
}


class ActivityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = ActivityRepository(db)
        self.costs = CostRepository(db)
        self.catalogs = CatalogRepository(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)
        self.subsidies = SubsidyRepository(db)
        self.photos = PhotoRepository(db)
        self.harvests = HarvestRepository(db)
        self.diseases = DiseaseRepository(db)

    def list_activities(
        self,
        owner_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        activity_type_id: UUID | None = None,
        scope_type: ScopeType | None = None,
        parcel_id: UUID | None = None,
        row_id: UUID | None = None,
        tree_id: UUID | None = None,
        status: ActivityStatus | None = None,
        limit: int | None = None,
    ) -> list[ActivityRead]:
        records = self.activities.list_for_owner(
            owner_id,
            date_from=date_from,
            date_to=date_to,
            activity_type_id=activity_type_id,
            scope_type=scope_type,
            parcel_id=parcel_id,
            row_id=row_id,
            tree_id=tree_id,
            status=status,
            limit=limit,
        )
        activity_ids = [row.id for row in records]
        harvest_map = {
            item.activity_id: item
            for item in self.harvests.list_by_activity_ids(activity_ids)
            if item.activity_id is not None
        }
        disease_map = {
            item.activity_id: item
            for item in self.diseases.list_by_activity_ids(activity_ids)
            if item.activity_id is not None
        }
        subsidy_map = {
            item.activity_id: item
            for item in self.subsidies.list_by_activity_ids(activity_ids)
            if item.activity_id is not None
        }
        plan_map = self._plan_items_by_ids(
            [row.plan_item_id for row in records if row.plan_item_id is not None]
        )
        return [
            self.to_activity_read(
                item,
                harvest=harvest_map.get(item.id),
                plan_item=plan_map.get(item.plan_item_id) if item.plan_item_id else None,
                disease_case=disease_map.get(item.id),
                subsidy=subsidy_map.get(item.id),
            )
            for item in records
        ]

    def get_activity(self, activity_id: UUID, owner_id: UUID) -> Activity:
        activity = self.activities.get_for_owner(activity_id, owner_id)
        if activity is None:
            raise NotFoundError("Aktivnost nije pronađena")
        return activity

    def create_activity(self, owner_id: UUID, payload: ActivityCreate, created_by_id: UUID) -> Activity:
        activity_type = self.catalogs.get_activity_type(payload.activity_type_id)
        if activity_type is None:
            raise NotFoundError("Tip aktivnosti nije pronađen")
        farm_id, parcel_id, row_id, tree_id, extra_row_ids = self._resolve_scope(owner_id, payload)
        if payload.status is not None:
            status = payload.status
        elif payload.performed_on > date.today():
            status = ActivityStatus.PLANNED
        else:
            status = ActivityStatus.COMPLETED
        line_items = self._normalize_line_items(payload)
        first_item = next((item for item in line_items if _is_work_quantity(item)), None)
        semantic_type = payload.semantic_type or _SLUG_TO_SEMANTIC.get(
            activity_type.slug, ActivitySemanticType.OTHER
        )
        observation_category = payload.observation_category
        observation_status = payload.observation_status
        observation_severity = payload.observation_severity
        if semantic_type in {
            ActivitySemanticType.OBSERVATION,
            ActivitySemanticType.PROBLEM,
            ActivitySemanticType.MONITORING,
        }:
            observation_category = observation_category or ObservationCategory.UNKNOWN
            observation_status = observation_status or ObservationStatus.NEW
        self._validate_links(
            owner_id,
            farm_id=farm_id,
            observation_id=payload.observation_id,
            follow_up_of_id=payload.follow_up_of_id,
            plan_item_id=payload.plan_item_id,
        )
        activity = Activity(
            activity_type_id=activity_type.id,
            title=(payload.title or activity_type.name).strip(),
            description=payload.description,
            performed_on=payload.performed_on,
            status=status,
            quantity=first_item.quantity if first_item else payload.quantity,
            unit=(first_item.unit.strip() if first_item and first_item.unit else None)
            or (payload.unit.strip() if payload.unit else None),
            line_items=[item.model_dump(mode="json") for item in line_items],
            extra_row_ids=extra_row_ids,
            notes=payload.notes,
            semantic_type=semantic_type,
            observation_category=observation_category,
            observation_severity=observation_severity,
            observation_status=observation_status,
            observation_id=payload.observation_id,
            plan_item_id=payload.plan_item_id,
            follow_up_of_id=payload.follow_up_of_id,
            created_by_id=created_by_id,
            scope_type=payload.scope_type,
            farm_id=farm_id,
            parcel_id=parcel_id,
            row_id=row_id,
            tree_id=tree_id,
        )
        self.activities.add(activity)
        self.db.flush()
        self._add_costs_from_line_items(activity, line_items, created_by_id, activity_type.slug)
        if payload.cost_amount and payload.cost_amount > 0 and not any(_is_eur_unit(item.unit) for item in line_items):
            self._add_inline_cost(activity, payload.cost_amount, created_by_id, description=activity.title)
        self.db.commit()
        loaded = self.activities.get_for_owner(activity.id, owner_id)
        assert loaded is not None
        try:
            from app.services.intelligence import IntelligenceService

            IntelligenceService(self.db).enqueue_activity_event(loaded.parcel_id, loaded.semantic_type)
        except Exception:  # noqa: BLE001
            pass
        return loaded

    def update_activity(self, activity_id: UUID, owner_id: UUID, payload: ActivityUpdate) -> Activity:
        activity = self.get_activity(activity_id, owner_id)
        if payload.status is not None:
            activity.status = payload.status
        if payload.performed_on is not None:
            activity.performed_on = payload.performed_on
        if payload.notes is not None:
            activity.notes = payload.notes
        if payload.description is not None:
            activity.description = payload.description
        if payload.semantic_type is not None:
            activity.semantic_type = payload.semantic_type
        if payload.observation_category is not None:
            activity.observation_category = payload.observation_category
        if payload.observation_severity is not None:
            activity.observation_severity = payload.observation_severity
        if payload.observation_status is not None:
            # User-initiated API only. AI must use apply_ai_observation_hint (blocks CONFIRMED).
            activity.observation_status = payload.observation_status
        data = payload.model_dump(exclude_unset=True)
        if "observation_id" in data or "follow_up_of_id" in data or "plan_item_id" in data:
            observation_id = data.get("observation_id", activity.observation_id)
            follow_up_of_id = data.get("follow_up_of_id", activity.follow_up_of_id)
            plan_item_id = data.get("plan_item_id", activity.plan_item_id)
            self._validate_links(
                owner_id,
                farm_id=activity.farm_id,
                observation_id=observation_id,
                follow_up_of_id=follow_up_of_id,
                plan_item_id=plan_item_id,
                self_id=activity.id,
            )
            if "observation_id" in data:
                activity.observation_id = observation_id
            if "follow_up_of_id" in data:
                activity.follow_up_of_id = follow_up_of_id
            if "plan_item_id" in data:
                activity.plan_item_id = plan_item_id
        self.db.commit()
        self.db.refresh(activity)
        loaded = self.activities.get_for_owner(activity.id, owner_id)
        assert loaded is not None
        return loaded

    def apply_ai_observation_hint(
        self,
        activity_id: UUID,
        owner_id: UUID,
        *,
        category: ObservationCategory | None = None,
        severity=None,
        status: ObservationStatus | None = None,
    ) -> Activity:
        """AI may suggest category/severity/status but never CONFIRMED."""
        if status == ObservationStatus.CONFIRMED:
            raise AppError(
                "AI ne sme automatski da potvrdi zapažanje (CONFIRMED)",
                status_code=422,
                code="ai_cannot_confirm",
            )
        activity = self.get_activity(activity_id, owner_id)
        if category is not None:
            activity.observation_category = category
        if severity is not None:
            activity.observation_severity = severity
        if status is not None:
            activity.observation_status = status
        self.db.commit()
        loaded = self.activities.get_for_owner(activity.id, owner_id)
        assert loaded is not None
        return loaded

    def add_cost(self, activity_id: UUID, owner_id: UUID, payload: CostCreate, created_by_id: UUID) -> Cost:
        activity = self.get_activity(activity_id, owner_id)
        category = self.catalogs.get_cost_category(payload.cost_category_id)
        if category is None:
            raise NotFoundError("Kategorija troška nije pronađena")
        cost = Cost(
            amount=payload.amount,
            currency=payload.currency.upper(),
            incurred_on=payload.incurred_on or activity.performed_on,
            description=payload.description.strip(),
            cost_category_id=category.id,
            activity_id=activity.id,
            source=CostSource.ACTIVITY,
            source_id=activity.id,
            notes=payload.notes,
            receipt_filename=payload.receipt_filename.strip() if payload.receipt_filename else None,
            created_by_id=created_by_id,
            scope_type=activity.scope_type,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            row_id=activity.row_id,
            tree_id=activity.tree_id,
        )
        self.costs.add(cost)
        self.db.flush()
        cost_id = cost.id
        self.db.commit()
        loaded = self.costs.get_for_owner(cost_id, owner_id)
        if loaded is None:
            raise NotFoundError("Trošak nije pronađen")
        return loaded

    def create_standalone_cost(
        self,
        owner_id: UUID,
        payload: CostStandaloneCreate,
        created_by_id: UUID,
    ) -> Cost:
        parcel = self.parcels.get_for_owner(payload.parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        category = self.catalogs.get_cost_category(payload.cost_category_id)
        if category is None:
            raise NotFoundError("Kategorija troška nije pronađena")
        if payload.activity_type_id is not None:
            activity_type = self.catalogs.get_activity_type(payload.activity_type_id)
        else:
            activity_type = self.catalogs.get_activity_type_by_slug("other")
        if activity_type is None:
            raise NotFoundError("Tip aktivnosti nije pronađen")
        title = payload.description.strip()
        activity = Activity(
            activity_type_id=activity_type.id,
            title=title,
            description=payload.notes,
            performed_on=payload.incurred_on,
            status=ActivityStatus.COMPLETED if payload.incurred_on <= date.today() else ActivityStatus.PLANNED,
            quantity=None,
            unit=None,
            line_items=[],
            extra_row_ids=[],
            notes=payload.notes,
            semantic_type=ActivitySemanticType.OTHER,
            created_by_id=created_by_id,
            scope_type=ScopeType.PARCEL,
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            row_id=None,
            tree_id=None,
        )
        self.activities.add(activity)
        self.db.flush()
        cost = Cost(
            amount=payload.amount.quantize(Decimal("0.01")),
            currency=payload.currency.upper(),
            incurred_on=payload.incurred_on,
            description=title,
            cost_category_id=category.id,
            activity_id=activity.id,
            source=CostSource.ACTIVITY,
            source_id=activity.id,
            notes=payload.notes,
            receipt_filename=None,
            created_by_id=created_by_id,
            scope_type=ScopeType.PARCEL,
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            row_id=None,
            tree_id=None,
        )
        self.costs.add(cost)
        self.db.flush()
        cost_id = cost.id
        self.db.commit()
        loaded = self.costs.get_for_owner(cost_id, owner_id)
        if loaded is None:
            raise NotFoundError("Trošak nije pronađen")
        return loaded

    def cost_summary(
        self,
        owner_id: UUID,
        parcel_id: UUID | None = None,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> CostSummaryRead:
        if parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
        today = date.today()
        year_start = date(today.year, 1, 1)
        month_start = date(today.year, today.month, 1)
        total = self.costs.sum_for_owner(
            owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
        )
        year_total = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_from=year_start)
        month_total = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_from=month_start)
        active_trees = self.trees.active_count(owner_id, parcel_id)
        area = self.parcels.total_area_hectares(owner_id, parcel_id)
        cost_per_tree = (total / active_trees).quantize(Decimal("0.01")) if active_trees else None
        cost_per_hectare = (total / area).quantize(Decimal("0.01")) if area else None
        yearly = self.costs.yearly_totals(
            owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
        )
        if date_from is not None or date_to is not None:
            start_year = date_from.year if date_from is not None else (min(yearly) if yearly else today.year)
            end_year = date_to.year if date_to is not None else today.year
            by_year = [
                YearAmount(year=year, amount=yearly.get(year, Decimal("0")))
                for year in range(start_year, end_year + 1)
            ]
        else:
            years = sorted(yearly) or [today.year]
            by_year = [
                YearAmount(year=year, amount=yearly.get(year, Decimal("0")))
                for year in range(years[0], today.year + 1)
            ]
        total_subsidies = self.subsidies.sum_for_owner(
            owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
        )
        subsidy_percent = _percent(total_subsidies, total) if total > 0 else None
        return CostSummaryRead(
            total_costs=total,
            current_year_costs=year_total,
            current_month_costs=month_total,
            cost_per_tree=cost_per_tree,
            cost_per_hectare=cost_per_hectare,
            active_tree_count=active_trees,
            area_hectares=area,
            by_category=[
                NamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
                for item, amount in self.costs.totals_by_category(
                    owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
                )
            ],
            by_activity_type=[
                NamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
                for item, amount in self.costs.totals_by_activity_type(
                    owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
                )
            ],
            by_year=by_year,
            parcel_id=parcel_id,
            total_subsidies=total_subsidies,
            subsidy_percent_of_costs=subsidy_percent,
        )

    def list_costs(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[CostItemRead]:
        if parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
        records = self.costs.list_for_owner(
            owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
        )
        return [self.to_cost_read(item) for item in records]

    def to_activity_read(
        self,
        activity: Activity,
        *,
        harvest: HarvestEvent | None = None,
        plan_item: PlanningPlanItem | None = None,
        disease_case: DiseaseCase | None = None,
        subsidy: Subsidy | None = None,
    ) -> ActivityRead:
        parcel_name, row_number, tree_public_id = self._scope_labels(
            activity.parcel_id, activity.row_id, activity.tree_id
        )
        costs = [self.to_cost_read(item) for item in activity.costs]
        total = sum((item.amount for item in activity.costs), Decimal("0"))
        currency = costs[0].currency if costs else "EUR"
        row_ids, row_numbers = self._activity_rows(activity)
        from app.services.disease import DiseaseService

        disease_service = DiseaseService(self.db)
        photos = [
            disease_service.to_photo_read(photo)
            for photo in self.photos.list_for_entity(AttachmentEntityType.ACTIVITY, activity.id)
        ]
        if harvest is None:
            linked = self.harvests.list_by_activity_ids([activity.id])
            harvest = linked[0] if linked else None
        if disease_case is None:
            linked_cases = self.diseases.list_by_activity_ids([activity.id])
            disease_case = linked_cases[0] if linked_cases else None
        if subsidy is None:
            linked_subsidies = self.subsidies.list_by_activity_ids([activity.id])
            subsidy = linked_subsidies[0] if linked_subsidies else None
        if plan_item is None and activity.plan_item_id is not None:
            plan_map = self._plan_items_by_ids([activity.plan_item_id])
            plan_item = plan_map.get(activity.plan_item_id)
        return ActivityRead(
            id=activity.id,
            created_at=activity.created_at,
            updated_at=activity.updated_at,
            activity_type=CatalogItemRead.model_validate(activity.activity_type),
            title=activity.title,
            description=activity.description,
            performed_on=activity.performed_on,
            status=activity.status,
            quantity=activity.quantity,
            unit=activity.unit,
            line_items=self._read_line_items(activity),
            notes=activity.notes,
            scope_type=activity.scope_type,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            row_id=activity.row_id,
            row_ids=row_ids,
            row_numbers=row_numbers,
            tree_id=activity.tree_id,
            parcel_name=parcel_name,
            row_number=row_numbers[0] if row_numbers else row_number,
            tree_public_id=tree_public_id,
            costs=costs,
            soil_analyses=[SoilLabAnalysisService(self.db).to_read(item) for item in activity.soil_analyses],
            photos=photos,
            harvest=self._harvest_snippet(harvest) if harvest is not None else None,
            plan_item=self._plan_item_snippet(plan_item) if plan_item is not None else None,
            disease_case=self._disease_snippet(disease_case) if disease_case is not None else None,
            subsidy=self._subsidy_snippet(subsidy) if subsidy is not None else None,
            total_cost=total,
            currency=currency,
            semantic_type=activity.semantic_type or ActivitySemanticType.OTHER,
            observation_category=activity.observation_category,
            observation_severity=activity.observation_severity,
            observation_status=activity.observation_status,
            observation_id=activity.observation_id,
            plan_item_id=activity.plan_item_id,
            follow_up_of_id=activity.follow_up_of_id,
        )

    def _plan_items_by_ids(self, item_ids: list[UUID]) -> dict[UUID, PlanningPlanItem]:
        ids = [item_id for item_id in item_ids if item_id is not None]
        if not ids:
            return {}
        stmt = (
            select(PlanningPlanItem)
            .where(PlanningPlanItem.id.in_(ids))
            .options(selectinload(PlanningPlanItem.plan))
        )
        items = list(self.db.scalars(stmt).unique().all())
        for item in items:
            if item.plan is not None:
                _ = item.plan.season
        return {item.id: item for item in items}

    def _plan_item_snippet(self, item: PlanningPlanItem) -> ActivityPlanItemSnippet:
        plan = item.plan
        season = plan.season if plan is not None else None
        products = [
            row
            for row in (item.evidence or [])
            if isinstance(row, dict) and row.get("type") in {"product", "irrigation"}
        ]
        return ActivityPlanItemSnippet(
            id=item.id,
            plan_id=item.plan_id,
            plan_type=plan.type.value if plan is not None else "protection",
            parcel_id=season.parcel_id if season is not None else None,
            year=season.year if season is not None else None,
            title=item.title,
            planned_date_from=item.planned_date_from,
            planned_date_to=item.planned_date_to,
            status=item.status.value if hasattr(item.status, "value") else str(item.status),
            description=item.description,
            products=products,
        )

    def _harvest_snippet(self, event: HarvestEvent) -> ActivityHarvestSnippet:
        parcel_name, row_number, tree_public_id = self._scope_labels(
            event.parcel_id, event.row_id, event.tree_id
        )
        if event.scope_type == ScopeType.TREE and tree_public_id:
            location = tree_public_id
        elif event.scope_type == ScopeType.ROW and row_number is not None:
            location = f"Red {row_number:02d}"
        else:
            location = parcel_name or "Parcela"
        return ActivityHarvestSnippet(
            id=event.id,
            parcel_id=event.parcel_id,
            harvested_on=event.harvested_on,
            location_label=location,
            gross_quantity=event.gross_quantity,
            loss_quantity=event.loss_quantity or Decimal("0"),
            net_quantity=event.net_quantity,
            unit=event.unit,
            quality_category=event.quality_category.value if event.quality_category else None,
            notes=event.notes,
        )

    def _disease_snippet(self, case: DiseaseCase) -> ActivityDiseaseSnippet:
        parcel_name, row_number, tree_public_id = self._scope_labels(
            case.parcel_id, case.row_id, case.tree_id
        )
        if case.tree_id is not None and tree_public_id:
            location = tree_public_id
        elif case.row_id is not None and row_number is not None:
            location = f"Red {row_number:02d}"
        else:
            location = parcel_name or "Parcela"
        return ActivityDiseaseSnippet(
            id=case.id,
            parcel_id=case.parcel_id,
            title=case.title,
            category=case.category.value if hasattr(case.category, "value") else str(case.category),
            severity=case.severity.value if hasattr(case.severity, "value") else str(case.severity),
            status=case.status.value if hasattr(case.status, "value") else str(case.status),
            detected_on=case.detected_on,
            location_label=location,
            notes=case.notes,
        )

    def _subsidy_snippet(self, subsidy: Subsidy) -> ActivitySubsidySnippet:
        return ActivitySubsidySnippet(
            id=subsidy.id,
            parcel_id=subsidy.parcel_id,
            title=subsidy.title,
            total_cost=subsidy.total_cost,
            subsidy_amount=subsidy.subsidy_amount,
            subsidy_percent=_percent(subsidy.subsidy_amount, subsidy.total_cost),
            currency=subsidy.currency,
            received_on=subsidy.received_on,
            notes=subsidy.notes,
        )

    def to_cost_read(self, cost: Cost) -> CostItemRead:
        parcel_name, row_number, tree_public_id = self._scope_labels(cost.parcel_id, cost.row_id, cost.tree_id)
        activity_title = cost.activity.title if cost.activity is not None else None
        activity_type_name = (
            cost.activity.activity_type.name if cost.activity is not None and cost.activity.activity_type else None
        )
        line_items = (
            [
                QuantityLineRead(
                    name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    volume=item.volume,
                    volume_unit=item.volume_unit,
                    amount=item.amount,
                )
                for item in self._read_line_items(cost.activity)
            ]
            if cost.activity is not None
            else []
        )
        return CostItemRead(
            id=cost.id,
            created_at=cost.created_at,
            updated_at=cost.updated_at,
            activity_id=cost.activity_id,
            source=cost.source.value if cost.source is not None else None,
            source_id=cost.source_id,
            description=cost.description,
            cost_category=CatalogItemRead.model_validate(cost.cost_category),
            amount=cost.amount,
            currency=cost.currency,
            incurred_on=cost.incurred_on,
            notes=cost.notes,
            receipt_filename=cost.receipt_filename,
            scope_type=cost.scope_type,
            farm_id=cost.farm_id,
            parcel_id=cost.parcel_id,
            row_id=cost.row_id,
            tree_id=cost.tree_id,
            activity_title=activity_title,
            activity_type_name=activity_type_name,
            activity_line_items=line_items,
            parcel_name=parcel_name,
            row_number=row_number,
            tree_public_id=tree_public_id,
        )

    def _resolve_scope(
        self, owner_id: UUID, payload: ActivityCreate
    ) -> tuple[UUID, UUID, UUID | None, UUID | None, list[str]]:
        parcel = self.parcels.get_for_owner(payload.parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        row_id: UUID | None = None
        tree_id: UUID | None = None
        extra_row_ids: list[str] = []
        if payload.scope_type in {ScopeType.ROW, ScopeType.TREE}:
            requested = list(dict.fromkeys(payload.row_ids or ([payload.row_id] if payload.row_id else [])))
            if payload.scope_type == ScopeType.TREE:
                requested = [payload.row_id] if payload.row_id else requested
            if not requested:
                raise AppError("Red je obavezan za ovaj obuhvat", status_code=422, code="invalid_scope")
            resolved: list[UUID] = []
            for item_id in requested:
                row = self.rows.get_for_parcel(parcel.id, item_id)
                if row is None:
                    raise NotFoundError("Red nije pronađen")
                resolved.append(row.id)
            row_id = resolved[0]
            extra_row_ids = [str(item) for item in resolved]
        if payload.scope_type == ScopeType.TREE:
            if payload.tree_id is None:
                raise AppError("Stablo je obavezno za ovaj obuhvat", status_code=422, code="invalid_scope")
            found = self.trees.get_for_parcel(parcel.id, payload.tree_id)
            if found is None:
                raise NotFoundError("Stablo nije pronađeno")
            tree, _row_number = found
            if row_id is not None and tree.row_id != row_id:
                raise AppError("Stablo ne pripada izabranom redu", status_code=422, code="invalid_scope")
            tree_id = tree.id
            extra_row_ids = [str(row_id)] if row_id else []
        return parcel.farm_id, parcel.id, row_id, tree_id, extra_row_ids

    def _normalize_line_items(self, payload: ActivityCreate) -> list[ActivityLineItem]:
        items = [item for item in payload.line_items if _line_item_has_value(item)]
        if items:
            return [
                ActivityLineItem(
                    name=_clean_text(item.name),
                    quantity=item.quantity,
                    unit=_clean_text(item.unit),
                    volume=item.volume,
                    volume_unit=_clean_text(item.volume_unit),
                    amount=item.amount,
                )
                for item in items
            ]
        if payload.quantity is not None or (payload.unit or "").strip():
            return [ActivityLineItem(quantity=payload.quantity, unit=_clean_text(payload.unit))]
        return []

    def _read_line_items(self, activity: Activity) -> list[ActivityLineItem]:
        raw = activity.line_items or []
        items: list[ActivityLineItem] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            parsed = ActivityLineItem(
                name=item.get("name"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                volume=item.get("volume"),
                volume_unit=item.get("volume_unit"),
                amount=item.get("amount"),
            )
            if _line_item_has_value(parsed):
                items.append(parsed)
        if items:
            return items
        if activity.quantity is not None or activity.unit:
            return [ActivityLineItem(quantity=activity.quantity, unit=activity.unit)]
        return []

    def _activity_rows(self, activity: Activity) -> tuple[list[UUID], list[int]]:
        stored: list[UUID] = []
        for item in activity.extra_row_ids or []:
            try:
                stored.append(item if isinstance(item, UUID) else UUID(str(item)))
            except ValueError:
                continue
        if activity.row_id and activity.row_id not in stored:
            stored.insert(0, activity.row_id)
        pairs: list[tuple[UUID, int]] = []
        for item_id in stored:
            row = self.db.get(Row, item_id)
            if row is not None:
                pairs.append((item_id, row.row_number))
        pairs.sort(key=lambda item: item[1])
        return [item[0] for item in pairs], [item[1] for item in pairs]

    def _add_costs_from_line_items(
        self,
        activity: Activity,
        line_items: list[ActivityLineItem],
        created_by_id: UUID,
        activity_slug: str,
    ) -> None:
        for item in line_items:
            amount = _line_item_cost(item)
            if amount is None:
                continue
            self._add_inline_cost(
                activity,
                amount,
                created_by_id,
                description=_clean_text(item.name) or activity.title,
                category_slug=_cost_category_for_line_item(activity_slug, item),
            )

    def _add_inline_cost(
        self,
        activity: Activity,
        amount: Decimal,
        created_by_id: UUID,
        description: str | None = None,
        category_slug: str = "other",
    ) -> None:
        categories = self.catalogs.list_cost_categories()
        category = (
            self.catalogs.get_cost_category_by_slug(category_slug)
            or self.catalogs.get_cost_category_by_slug("other")
            or (categories[0] if categories else None)
        )
        if category is None:
            raise AppError("Kategorija troška nije pronađena", status_code=422, code="missing_cost_category")
        cost = Cost(
            amount=amount,
            currency="EUR",
            incurred_on=activity.performed_on,
            description=description or activity.title,
            cost_category_id=category.id,
            activity_id=activity.id,
            source=CostSource.ACTIVITY,
            source_id=activity.id,
            created_by_id=created_by_id,
            scope_type=activity.scope_type,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            row_id=activity.row_id,
            tree_id=activity.tree_id,
        )
        self.costs.add(cost)

    def _scope_labels(
        self,
        parcel_id: UUID | None,
        row_id: UUID | None,
        tree_id: UUID | None,
    ) -> tuple[str | None, int | None, str | None]:
        parcel_name = None
        row_number = None
        tree_public_id = None
        if parcel_id is not None:
            parcel = self.db.get(Parcel, parcel_id)
            parcel_name = parcel.name if parcel else None
        if row_id is not None:
            row = self.db.get(Row, row_id)
            row_number = row.row_number if row else None
        if tree_id is not None:
            tree = self.db.get(Tree, tree_id)
            tree_public_id = tree.public_id if tree else None
        return parcel_name, row_number, tree_public_id

    def _validate_links(
        self,
        owner_id: UUID,
        *,
        farm_id: UUID,
        observation_id: UUID | None,
        follow_up_of_id: UUID | None,
        plan_item_id: UUID | None,
        self_id: UUID | None = None,
    ) -> None:
        for label, linked_id in (("observation_id", observation_id), ("follow_up_of_id", follow_up_of_id)):
            if linked_id is None:
                continue
            if self_id is not None and linked_id == self_id:
                raise AppError(f"{label} ne može da ukazuje na isti zapis", status_code=422, code="invalid_link")
            linked = self.activities.get_for_owner(linked_id, owner_id)
            if linked is None or linked.farm_id != farm_id:
                raise NotFoundError("Povezani zapis nije pronađen")
        if plan_item_id is not None:
            from app.models.planning import PlanningPlan, PlanningPlanItem, PlanningSeason

            item = self.db.get(PlanningPlanItem, plan_item_id)
            if item is None:
                raise NotFoundError("Stavka plana nije pronađena")
            plan = self.db.get(PlanningPlan, item.plan_id)
            if plan is None:
                raise NotFoundError("Plan nije pronađen")
            season = self.db.get(PlanningSeason, plan.season_id)
            if season is None:
                raise NotFoundError("Sezona plana nije pronađena")
            parcel = self.parcels.get_for_owner(season.parcel_id, owner_id)
            if parcel is None or parcel.farm_id != farm_id:
                raise NotFoundError("Stavka plana nije pronađena")


def _is_eur_unit(unit: str | None) -> bool:
    value = (unit or "").strip().upper().replace("€", "EUR")
    return value in {"EUR", "EURO"}


def _clean_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _line_item_has_value(item: ActivityLineItem) -> bool:
    return bool(
        _clean_text(item.name)
        or item.quantity is not None
        or _clean_text(item.unit)
        or item.volume is not None
        or _clean_text(item.volume_unit)
        or item.amount is not None
    )


def _is_work_quantity(item: ActivityLineItem) -> bool:
    return item.quantity is not None and not _is_eur_unit(item.unit)


def _line_item_cost(item: ActivityLineItem) -> Decimal | None:
    if item.amount is not None and item.amount > 0:
        return item.amount
    if _is_eur_unit(item.unit) and item.quantity is not None and item.quantity > 0:
        return item.quantity
    return None


def _cost_category_for_activity(slug: str) -> str:
    return {
        "irrigation": "fuel",
        "spraying": "plant_protection",
        "fertilization": "fertilizers",
        "planting": "planting_material",
        "harvesting": "harvesting",
        "maintenance": "maintenance",
    }.get(slug, "other")


def _is_fuel_line_item(item: ActivityLineItem) -> bool:
    name = (item.name or "").strip().casefold()
    return name in {"nafta", "dizel", "diesel", "gorivo"}


def _cost_category_for_line_item(activity_slug: str, item: ActivityLineItem) -> str:
    if activity_slug == "irrigation" and not _is_fuel_line_item(item):
        return "equipment"
    return _cost_category_for_activity(activity_slug)
