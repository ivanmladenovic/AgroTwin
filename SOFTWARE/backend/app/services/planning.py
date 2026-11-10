from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.activity import Activity, ActivityType
from app.models.enums import (
    PlanningExpertReviewStatus,
    PlanningItemKind,
    PlanningItemSource,
    PlanningItemStatus,
    PlanningPlanStatus,
    PlanningPlanType,
    PlanningPriorityLevel,
    PlanningScopeType,
    PlanningSeasonStatus,
    PlanningStream,
)
from app.models.planning import PlanningPlan, PlanningPlanItem, PlanningSeason
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.parcel import ParcelRepository
from app.repositories.planning import (
    PlanningPlanItemRepository,
    PlanningPlanRepository,
    PlanningSeasonRepository,
)
from app.repositories.soil_lab import SoilLabAnalysisRepository
from app.schemas.planning import (
    ExpertReviewDecisionRequest,
    ExpertReviewRead,
    ExpertReviewSubmitRequest,
    IrrigationPlanGenerateRequest,
    NutritionPlanGenerateRequest,
    PlanningActivitySnippet,
    PlanningCopyRequest,
    PlanningDashboard,
    PlanningDomainCard,
    PlanningParcelSummary,
    PlanningPlanCreate,
    PlanningPlanItemCreate,
    PlanningPlanItemRead,
    PlanningPlanItemUpdate,
    PlanningPlanRead,
    PlanningPreviousPlanSnippet,
    PlanningPriorityItem,
    PlanningSeasonCreate,
    PlanningSeasonRead,
    PlanningSeasonUpdate,
    PlanningSoilSnippet,
    ProtectionPlanGenerateRequest,
)
from app.services.expert_review import ExpertReviewService
from app.services.irrigation_plan import IrrigationPlanEngine
from app.services.nutrition_plan import NutritionPlanEngine
from app.services.plan_draft import PRIORITY_SCORE
from app.services.protection_plan import ProtectionPlanEngine

DISPLAY_STATUS = {
    PlanningExpertReviewStatus.NOT_REQUIRED: ("proposal", "PREDLOG"),
    PlanningExpertReviewStatus.PENDING: ("pending_review", "ČEKA STRUČNU PROVERU"),
    PlanningExpertReviewStatus.APPROVED: ("approved", "STRUČNO ODOBRENO"),
    PlanningExpertReviewStatus.MODIFIED: ("modified", "STRUČNO IZMENJENO"),
    PlanningExpertReviewStatus.REJECTED: ("rejected", "ODBIJENO"),
}

_PRIORITY_RANK = {
    PlanningPriorityLevel.HIGH: 0,
    PlanningPriorityLevel.MEDIUM: 1,
    PlanningPriorityLevel.LOW: 2,
    PlanningPriorityLevel.INFO: 3,
}

# Items in these statuses are historical proposals worth carrying forward.
_COPYABLE_ITEM_STATUSES = {
    PlanningItemStatus.PLANNED,
    PlanningItemStatus.MONITOR,
    PlanningItemStatus.OBSERVED,
    PlanningItemStatus.NEEDS_REVIEW,
    PlanningItemStatus.APPROVED,
    PlanningItemStatus.COMPLETED,
}


def _shift_year(value: date | None, year: int) -> date | None:
    if value is None:
        return None
    try:
        return value.replace(year=year)
    except ValueError:
        # Feb 29 → Feb 28 in non-leap years
        return value.replace(year=year, day=28)


class PlanningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.seasons = PlanningSeasonRepository(db)
        self.plans = PlanningPlanRepository(db)
        self.items = PlanningPlanItemRepository(db)
        self.parcels = ParcelRepository(db)
        self.soil_lab = SoilLabAnalysisRepository(db)

    def parcel_summary(self, owner_id: UUID, parcel_id: UUID) -> PlanningParcelSummary:
        parcel = self._parcel(owner_id, parcel_id)
        seasons = self.seasons.list_for_parcel(owner_id, parcel_id)
        season_reads = [self.to_season_read(item, include_plans=True) for item in seasons]

        previous_plans: list[PlanningPreviousPlanSnippet] = []
        for season in seasons:
            for plan in season.plans:
                previous_plans.append(
                    PlanningPreviousPlanSnippet(
                        season_id=season.id,
                        year=season.year,
                        plan_id=plan.id,
                        plan_type=plan.type,
                        status=plan.status,
                        item_count=len(plan.items),
                    )
                )

        soil_rows = self.soil_lab.list_for_parcel(parcel_id)
        latest_soil = None
        verified = self.soil_lab.get_latest_verified(parcel_id)
        row = verified or (soil_rows[0] if soil_rows else None)
        if row:
            latest_soil = PlanningSoilSnippet(
                id=row.id,
                sampled_on=row.sampled_on,
                original_filename=row.original_filename,
                tree_id=row.tree_id,
                verification_status=row.verification_status.value if row.verification_status else None,
                laboratory_name=row.laboratory_name,
                result_count=len(row.results or []),
                source_kind="laboratory",
            )

        recent = self._recent_activities(parcel_id, limit=8)
        well_raw = parcel.well_location.value if parcel.well_location else None
        well = _well_location_sr(well_raw)
        has_irrigation = bool(getattr(parcel, "has_irrigation", False))
        irrigation_type_raw = (
            parcel.irrigation_type.value if getattr(parcel, "irrigation_type", None) is not None else None
        )
        irrigation_type = _irrigation_type_sr(irrigation_type_raw)
        if has_irrigation:
            irrigation_hint = f"Sistem: {irrigation_type or 'tip nije unet'}"
            if well:
                irrigation_hint += f" · bunarište: {well}"
        else:
            irrigation_hint = "Nema označenog sistema" + (f" · bunarište: {well}" if well else "")

        varieties = _parcel_variety_names(parcel)
        if parcel.production_method.value == "organic":
            if parcel.organic_scope.value == "entire_parcel":
                organic_status = "Organska — cela parcela"
            elif parcel.organic_scope.value == "part_of_parcel":
                organic_status = "Organska — deo parcele"
            else:
                organic_status = "Organska"
            organic_note = ""
        else:
            organic_status = "Konvencionalna"
            organic_note = ""

        return PlanningParcelSummary(
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            farm_id=parcel.farm_id,
            area_hectares=float(parcel.area_hectares) if parcel.area_hectares is not None else None,
            default_variety=parcel.default_variety,
            varieties=varieties,
            default_planting_year=parcel.default_planting_year,
            well_location=well,
            irrigation_hint=irrigation_hint,
            has_irrigation=has_irrigation,
            irrigation_type=irrigation_type,
            organic_status=organic_status,
            organic_status_note=organic_note,
            latest_soil_analysis=latest_soil,
            recent_activities=recent,
            seasons=season_reads,
            previous_plans=previous_plans,
        )

    def list_seasons(self, owner_id: UUID, parcel_id: UUID) -> list[PlanningSeasonRead]:
        self._parcel(owner_id, parcel_id)
        return [self.to_season_read(item, include_plans=True) for item in self.seasons.list_for_parcel(owner_id, parcel_id)]

    def get_season(self, season_id: UUID, owner_id: UUID) -> PlanningSeasonRead:
        season = self._get_season(season_id, owner_id)
        return self.to_season_read(season, include_plans=True)

    def create_season(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        payload: PlanningSeasonCreate,
        created_by_id: UUID,
    ) -> PlanningSeason:
        parcel = self._parcel(owner_id, parcel_id)
        existing = self.seasons.get_by_parcel_year(owner_id, parcel_id, payload.year)
        if existing is not None:
            raise AppError(
                f"Sezona {payload.year} već postoji za ovu parcelu.",
                status_code=409,
                code="planning_season_exists",
            )

        source: PlanningSeason | None = None
        if payload.copy_from_season_id is not None:
            source = self._get_season(payload.copy_from_season_id, owner_id)
            if source.parcel_id != parcel_id:
                raise AppError("Izvorna sezona nije na istoj parceli.", status_code=422, code="source_parcel_mismatch")
        elif payload.copy_previous_plan:
            source = self._previous_season(owner_id, parcel_id, payload.year)

        season = PlanningSeason(
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            year=payload.year,
            status=payload.status,
            copied_from_season_id=source.id if source else None,
            created_by_id=created_by_id,
        )
        self.seasons.add(season)
        self.db.flush()

        if source is not None:
            self._copy_plans_from_season(season, source)

        self.db.commit()
        self.db.expire_all()
        loaded = self.seasons.get_for_owner(season.id, owner_id)
        assert loaded is not None
        return loaded

    def update_season(self, season_id: UUID, owner_id: UUID, payload: PlanningSeasonUpdate) -> PlanningSeason:
        season = self._get_season(season_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] is not None:
            season.status = data["status"]
        self.db.commit()
        loaded = self.seasons.get_for_owner(season.id, owner_id)
        assert loaded is not None
        return loaded

    def copy_from_season(
        self,
        season_id: UUID,
        owner_id: UUID,
        payload: PlanningCopyRequest,
    ) -> PlanningSeason:
        target = self._get_season(season_id, owner_id)
        source = self._get_season(payload.source_season_id, owner_id)
        if source.parcel_id != target.parcel_id:
            raise AppError("Izvorna sezona nije na istoj parceli.", status_code=422, code="source_parcel_mismatch")
        if source.id == target.id:
            raise AppError("Ne možete kopirati sezonu u samu sebe.", status_code=422, code="same_season")
        if not source.plans:
            # Empty previous season — no-op copy, still record provenance link if missing.
            if target.copied_from_season_id is None:
                target.copied_from_season_id = source.id
            self.db.commit()
            self.db.expire_all()
            loaded = self.seasons.get_for_owner(target.id, owner_id)
            assert loaded is not None
            return loaded

        self._copy_plans_from_season(target, source)
        if target.copied_from_season_id is None:
            target.copied_from_season_id = source.id
        self.db.commit()
        self.db.expire_all()
        loaded = self.seasons.get_for_owner(target.id, owner_id)
        assert loaded is not None
        return loaded

    def create_plan(
        self,
        season_id: UUID,
        owner_id: UUID,
        payload: PlanningPlanCreate,
    ) -> PlanningPlan:
        season = self._get_season(season_id, owner_id)
        existing = [
            plan
            for plan in season.plans
            if plan.type == payload.type and plan.version == payload.version
        ]
        if existing:
            raise AppError(
                "Plan tog tipa i verzije već postoji u sezoni.",
                status_code=409,
                code="planning_plan_exists",
            )
        plan = PlanningPlan(
            planning_season_id=season.id,
            type=payload.type,
            status=payload.status,
            version=payload.version,
        )
        self.plans.add(plan)
        self.db.commit()
        loaded = self.plans.get_for_owner(plan.id, owner_id)
        assert loaded is not None
        return loaded

    def get_plan(self, plan_id: UUID, owner_id: UUID) -> PlanningPlanRead:
        plan = self._get_plan(plan_id, owner_id)
        return self.to_plan_read(plan, include_items=True)

    def list_plans(self, season_id: UUID, owner_id: UUID) -> list[PlanningPlanRead]:
        self._get_season(season_id, owner_id)
        return [self.to_plan_read(plan, include_items=False) for plan in self.plans.list_for_season(owner_id, season_id)]

    def create_item(
        self,
        plan_id: UUID,
        owner_id: UUID,
        payload: PlanningPlanItemCreate,
    ) -> PlanningPlanItem:
        plan = self._get_plan(plan_id, owner_id)
        season = self._get_season(plan.planning_season_id, owner_id)
        scope_id = payload.scope_id or season.parcel_id
        self._validate_scope(owner_id, season.parcel_id, payload.scope_type, scope_id)

        expert = payload.expert_review_status
        status = payload.status
        if payload.source == PlanningItemSource.AI:
            if status == PlanningItemStatus.APPROVED:
                raise AppError("AI stavka ne sme automatski biti odobrena.", status_code=422, code="ai_not_approved")
            if expert == PlanningExpertReviewStatus.NOT_REQUIRED:
                expert = PlanningExpertReviewStatus.PENDING

        item = PlanningPlanItem(
            plan_id=plan.id,
            scope_type=payload.scope_type,
            scope_id=scope_id,
            title=payload.title.strip(),
            description=(payload.description or "").strip() or None,
            planned_date_from=payload.planned_date_from,
            planned_date_to=payload.planned_date_to,
            priority=PRIORITY_SCORE.get(payload.priority_level, payload.priority),
            priority_level=payload.priority_level,
            priority_reason=payload.priority_reason,
            item_kind=payload.item_kind,
            stream=payload.stream,
            reason=payload.reason,
            evidence=payload.evidence or [],
            missing_data=payload.missing_data or [],
            related_activity_id=payload.related_activity_id,
            status=status,
            source=payload.source,
            expert_review_status=expert,
        )
        self.items.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(
        self,
        plan_id: UUID,
        item_id: UUID,
        owner_id: UUID,
        payload: PlanningPlanItemUpdate,
    ) -> PlanningPlanItem:
        plan = self._get_plan(plan_id, owner_id)
        item = next((row for row in plan.items if row.id == item_id), None)
        if item is None:
            raise NotFoundError("Stavka plana nije pronađena")
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            item.title = data["title"].strip()
        if "description" in data:
            item.description = (data["description"] or "").strip() or None
        if "planned_date_from" in data:
            item.planned_date_from = data["planned_date_from"]
        if "planned_date_to" in data:
            item.planned_date_to = data["planned_date_to"]
        if "priority_level" in data and data["priority_level"] is not None:
            item.priority_level = data["priority_level"]
            item.priority = PRIORITY_SCORE[data["priority_level"]]
        if "priority_reason" in data:
            item.priority_reason = data["priority_reason"]
        if "status" in data and data["status"] is not None:
            item.status = data["status"]
        if "expert_review_status" in data and data["expert_review_status"] is not None:
            item.expert_review_status = data["expert_review_status"]
        if "related_activity_id" in data:
            item.related_activity_id = data["related_activity_id"]
        self.db.commit()
        self.db.refresh(item)
        return item

    def generate_protection_plan(
        self,
        season_id: UUID,
        owner_id: UUID,
        payload: ProtectionPlanGenerateRequest | None = None,
    ) -> PlanningPlanRead:
        body = payload or ProtectionPlanGenerateRequest()
        plan = ProtectionPlanEngine(self.db).generate(
            season_id,
            owner_id,
            replace_generated=body.replace_generated,
            include_knowledge=body.include_knowledge,
        )
        return self.to_plan_read(plan, include_items=True)

    def generate_nutrition_plan(
        self,
        season_id: UUID,
        owner_id: UUID,
        payload: NutritionPlanGenerateRequest | None = None,
    ) -> PlanningPlanRead:
        body = payload or NutritionPlanGenerateRequest()
        plan = NutritionPlanEngine(self.db).generate(
            season_id,
            owner_id,
            replace_generated=body.replace_generated,
            include_knowledge=body.include_knowledge,
        )
        return self.to_plan_read(plan, include_items=True)

    def generate_irrigation_plan(
        self,
        season_id: UUID,
        owner_id: UUID,
        payload: IrrigationPlanGenerateRequest | None = None,
    ) -> PlanningPlanRead:
        body = payload or IrrigationPlanGenerateRequest()
        plan = IrrigationPlanEngine(self.db).generate(
            season_id,
            owner_id,
            replace_generated=body.replace_generated,
            include_knowledge=body.include_knowledge,
        )
        return self.to_plan_read(plan, include_items=True)

    def to_season_read(self, season: PlanningSeason, *, include_plans: bool) -> PlanningSeasonRead:
        parcel = self.parcels.get_by_id(season.parcel_id)
        plans = []
        if include_plans:
            plans = [self.to_plan_read(plan, include_items=False) for plan in season.plans]
        return PlanningSeasonRead(
            id=season.id,
            created_at=season.created_at,
            updated_at=season.updated_at,
            farm_id=season.farm_id,
            parcel_id=season.parcel_id,
            parcel_name=parcel.name if parcel else None,
            year=season.year,
            status=season.status,
            copied_from_season_id=season.copied_from_season_id,
            created_by_id=season.created_by_id,
            plans=plans,
        )

    def to_plan_read(self, plan: PlanningPlan, *, include_items: bool) -> PlanningPlanRead:
        items = [self.to_item_read(item) for item in plan.items] if include_items else []
        return PlanningPlanRead(
            id=plan.id,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            planning_season_id=plan.planning_season_id,
            type=plan.type,
            status=plan.status,
            version=plan.version,
            item_count=len(plan.items),
            items=items,
        )

    def to_item_read(self, item: PlanningPlanItem) -> PlanningPlanItemRead:
        expert_status = getattr(item, "expert_review_status", None) or PlanningExpertReviewStatus.NOT_REQUIRED
        display_key, display_label = DISPLAY_STATUS.get(expert_status, ("proposal", "PREDLOG"))
        if expert_status == PlanningExpertReviewStatus.NOT_REQUIRED and item.source in {
            PlanningItemSource.SYSTEM,
            PlanningItemSource.AGRONOMIC_RULE,
            PlanningItemSource.AI,
        }:
            display_key, display_label = "proposal", "PREDLOG"
        reviews = [
            ExpertReviewRead(
                id=row.id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                plan_item_id=row.plan_item_id,
                farm_id=row.farm_id,
                requested_by_id=row.requested_by_id,
                reviewer_id=row.reviewer_id,
                reviewer_name=row.reviewer_name,
                status=row.status,
                reviewed_at=row.reviewed_at,
                comment=row.comment,
                original_recommendation_snapshot=dict(row.original_recommendation_snapshot or {}),
                reviewed_recommendation_snapshot=dict(row.reviewed_recommendation_snapshot or {})
                if row.reviewed_recommendation_snapshot
                else None,
            )
            for row in (getattr(item, "expert_reviews", None) or [])
        ]
        plan = getattr(item, "plan", None)
        season = getattr(plan, "season", None) if plan is not None else None
        provenance = {
            "parcel_id": str(season.parcel_id) if season else None,
            "season_year": season.year if season else None,
            "scope_type": item.scope_type.value if item.scope_type else None,
            "scope_id": str(item.scope_id),
            "plan_type": plan.type.value if plan and plan.type else None,
            "data_used": {
                "evidence_count": len(item.evidence or []),
                "missing_data": list(item.missing_data or []),
                "related_activity_id": str(item.related_activity_id) if item.related_activity_id else None,
            },
            "previous_history": {
                "source_season_id": str(item.source_season_id) if item.source_season_id else None,
                "source_plan_id": str(item.source_plan_id) if item.source_plan_id else None,
                "source_plan_item_id": str(item.source_plan_item_id) if item.source_plan_item_id else None,
                "item_source": item.source.value if item.source else None,
            },
            "knowledge_sources": [
                ev for ev in (item.evidence or []) if isinstance(ev, dict) and ev.get("document_title")
            ],
            "reviewer": reviews[-1].reviewer_name if reviews else None,
            "uncertainty": list(item.missing_data or []),
        }
        requires = expert_status in {
            PlanningExpertReviewStatus.PENDING,
            PlanningExpertReviewStatus.NOT_REQUIRED,
        } and item.source != PlanningItemSource.USER
        if expert_status in {
            PlanningExpertReviewStatus.APPROVED,
            PlanningExpertReviewStatus.MODIFIED,
            PlanningExpertReviewStatus.REJECTED,
        }:
            requires = False
        if expert_status == PlanningExpertReviewStatus.PENDING:
            requires = True
        return PlanningPlanItemRead(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            plan_id=item.plan_id,
            scope_type=item.scope_type,
            scope_id=item.scope_id,
            title=item.title,
            description=item.description,
            planned_date_from=item.planned_date_from,
            planned_date_to=item.planned_date_to,
            priority=item.priority,
            priority_level=getattr(item, "priority_level", None) or PlanningPriorityLevel.INFO,
            priority_reason=getattr(item, "priority_reason", None),
            item_kind=getattr(item, "item_kind", None) or PlanningItemKind.MONITORING,
            stream=getattr(item, "stream", None) or PlanningStream.PREVENTIVE,
            reason=getattr(item, "reason", None),
            evidence=list(getattr(item, "evidence", None) or []),
            missing_data=list(getattr(item, "missing_data", None) or []),
            related_activity_id=getattr(item, "related_activity_id", None),
            status=item.status,
            source=item.source,
            expert_review_status=expert_status,
            source_season_id=item.source_season_id,
            source_plan_id=item.source_plan_id,
            source_plan_item_id=item.source_plan_item_id,
            display_status=display_key,
            display_status_label=display_label,
            requires_expert_review=requires or expert_status == PlanningExpertReviewStatus.PENDING,
            provenance=provenance,
            expert_reviews=reviews,
        )

    def dashboard(self, owner_id: UUID, parcel_id: UUID, year: int) -> PlanningDashboard:
        parcel = self._parcel(owner_id, parcel_id)
        seasons = self.seasons.list_for_parcel(owner_id, parcel_id)
        season = next((item for item in seasons if item.year == year), None)
        previous = next((item for item in seasons if item.year < year), None)
        summary = self.parcel_summary(owner_id, parcel_id)

        def empty_card(plan_type: PlanningPlanType) -> PlanningDomainCard:
            return PlanningDomainCard(
                plan_type=plan_type,
                status="nema plana",
                next_actions=["Generiši nacrt plana"],
            )

        cards = {
            PlanningPlanType.PROTECTION: empty_card(PlanningPlanType.PROTECTION),
            PlanningPlanType.NUTRITION: empty_card(PlanningPlanType.NUTRITION),
            PlanningPlanType.IRRIGATION: empty_card(PlanningPlanType.IRRIGATION),
        }
        priorities: list[PlanningPriorityItem] = []

        if season is not None:
            for plan in season.plans:
                pending = sum(
                    1
                    for item in plan.items
                    if item.expert_review_status == PlanningExpertReviewStatus.PENDING
                )
                reviews = sum(
                    1
                    for item in plan.items
                    if item.expert_review_status
                    in {
                        PlanningExpertReviewStatus.PENDING,
                        PlanningExpertReviewStatus.APPROVED,
                        PlanningExpertReviewStatus.MODIFIED,
                        PlanningExpertReviewStatus.REJECTED,
                    }
                )
                observations = sum(
                    1
                    for item in plan.items
                    if item.stream == PlanningStream.REACTIVE and item.status != PlanningItemStatus.CANCELLED
                )
                next_actions = [
                    item.title
                    for item in sorted(
                        [
                            row
                            for row in plan.items
                            if row.status
                            not in {PlanningItemStatus.COMPLETED, PlanningItemStatus.CANCELLED}
                        ],
                        key=lambda row: (
                            _PRIORITY_RANK.get(row.priority_level, 9),
                            row.planned_date_from or date.max,
                        ),
                    )[:3]
                ]
                soil_note = None
                system_note = None
                if plan.type == PlanningPlanType.NUTRITION:
                    soil = summary.latest_soil_analysis
                    soil_note = (
                        f"{soil.original_filename} ({soil.verification_status})"
                        if soil
                        else "Nema lab analize"
                    )
                if plan.type == PlanningPlanType.IRRIGATION:
                    system_note = summary.irrigation_hint
                cards[plan.type] = PlanningDomainCard(
                    plan_type=plan.type,
                    plan_id=plan.id,
                    status=plan.status.value,
                    next_actions=next_actions or ["Nema otvorenih akcija"],
                    active_observations=observations,
                    expert_review_pending=pending,
                    expert_review_count=reviews,
                    soil_analysis=soil_note,
                    system_status=system_note,
                    item_count=len(plan.items),
                )
                for item in plan.items:
                    if item.status in {PlanningItemStatus.COMPLETED, PlanningItemStatus.CANCELLED}:
                        if item.expert_review_status != PlanningExpertReviewStatus.REJECTED:
                            continue
                    read = self.to_item_read(item)
                    priorities.append(
                        PlanningPriorityItem(
                            plan_item_id=item.id,
                            plan_id=plan.id,
                            plan_type=plan.type,
                            title=item.title,
                            display_status=read.display_status,
                            display_status_label=read.display_status_label,
                            priority_level=item.priority_level,
                            planned_date_from=item.planned_date_from,
                            scope_type=item.scope_type,
                            scope_id=item.scope_id,
                            expert_review_status=item.expert_review_status,
                            reason=item.reason or item.priority_reason,
                        )
                    )

        priorities.sort(
            key=lambda row: (
                0 if row.expert_review_status == PlanningExpertReviewStatus.PENDING else 1,
                _PRIORITY_RANK.get(row.priority_level, 9),
                row.planned_date_from or date.max,
            )
        )

        return PlanningDashboard(
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            year=year,
            season_id=season.id if season else None,
            season_status=season.status if season else None,
            previous_season=self.to_season_read(previous, include_plans=True) if previous else None,
            priorities=priorities[:20],
            protection=cards[PlanningPlanType.PROTECTION],
            nutrition=cards[PlanningPlanType.NUTRITION],
            irrigation=cards[PlanningPlanType.IRRIGATION],
        )

    def finish_season(self, season_id: UUID, owner_id: UUID) -> PlanningSeason:
        season = self._get_season(season_id, owner_id)
        season.status = PlanningSeasonStatus.COMPLETED
        self.db.commit()
        self.db.expire_all()
        loaded = self.seasons.get_for_owner(season.id, owner_id)
        assert loaded is not None
        return loaded

    def submit_expert_review(
        self,
        plan_id: UUID,
        item_id: UUID,
        owner_id: UUID,
        requester,
        payload: ExpertReviewSubmitRequest | None = None,
    ) -> PlanningPlanItemRead:
        ExpertReviewService(self.db).submit(plan_id, item_id, owner_id, requester, payload)
        plan = self._get_plan(plan_id, owner_id)
        item = next(row for row in plan.items if row.id == item_id)
        return self.to_item_read(item)

    def decide_expert_review(
        self,
        plan_id: UUID,
        item_id: UUID,
        review_id: UUID,
        owner_id: UUID,
        reviewer,
        payload: ExpertReviewDecisionRequest,
    ) -> PlanningPlanItemRead:
        ExpertReviewService(self.db).decide(plan_id, item_id, review_id, owner_id, reviewer, payload)
        plan = self._get_plan(plan_id, owner_id)
        item = next(row for row in plan.items if row.id == item_id)
        return self.to_item_read(item)

    def _copy_plans_from_season(self, target: PlanningSeason, source: PlanningSeason) -> None:
        existing_types = {plan.type for plan in target.plans}
        for source_plan in source.plans:
            if source_plan.type in existing_types:
                # Do not overwrite an already-created plan of the same type.
                continue
            new_plan = PlanningPlan(
                planning_season_id=target.id,
                type=source_plan.type,
                status=PlanningPlanStatus.DRAFT,
                version=1,
            )
            self.plans.add(new_plan)
            self.db.flush()
            existing_types.add(source_plan.type)

            for source_item in source_plan.items:
                if source_item.status not in _COPYABLE_ITEM_STATUSES:
                    continue
                if source_item.status == PlanningItemStatus.CANCELLED:
                    continue
                date_from = _shift_year(source_item.planned_date_from, target.year)
                date_to = _shift_year(source_item.planned_date_to, target.year)

                copied = PlanningPlanItem(
                    plan_id=new_plan.id,
                    scope_type=source_item.scope_type,
                    scope_id=source_item.scope_id,
                    title=source_item.title,
                    description=source_item.description,
                    planned_date_from=date_from,
                    planned_date_to=date_to,
                    priority=source_item.priority,
                    priority_level=getattr(source_item, "priority_level", None) or PlanningPriorityLevel.INFO,
                    priority_reason=(
                        f"Preuzeto iz sezone {source.year} kao istorijski predlog — nije trenutna činjenica."
                    ),
                    item_kind=getattr(source_item, "item_kind", None) or PlanningItemKind.MONITORING,
                    stream=getattr(source_item, "stream", None) or PlanningStream.PREVENTIVE,
                    reason=getattr(source_item, "reason", None)
                    or "Kopirano iz prethodne sezone (PREVIOUS_PLAN).",
                    evidence=list(getattr(source_item, "evidence", None) or []),
                    missing_data=[],
                    related_activity_id=None,
                    status=PlanningItemStatus.PLANNED,
                    source=PlanningItemSource.PREVIOUS_PLAN,
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                    source_season_id=source.id,
                    source_plan_id=source_plan.id,
                    source_plan_item_id=source_item.id,
                )
                self.items.add(copied)
            self.db.flush()

    def _previous_season(self, owner_id: UUID, parcel_id: UUID, year: int) -> PlanningSeason | None:
        seasons = self.seasons.list_for_parcel(owner_id, parcel_id)
        earlier = [item for item in seasons if item.year < year]
        return earlier[0] if earlier else None

    def _recent_activities(self, parcel_id: UUID, *, limit: int) -> list[PlanningActivitySnippet]:
        stmt = (
            select(Activity, ActivityType)
            .join(ActivityType, Activity.activity_type_id == ActivityType.id)
            .where(Activity.parcel_id == parcel_id)
            .order_by(Activity.performed_on.desc(), Activity.created_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [
            PlanningActivitySnippet(
                id=activity.id,
                title=activity.title,
                performed_on=activity.performed_on,
                activity_type=activity_type.name if activity_type else None,
                status=activity.status.value if hasattr(activity.status, "value") else str(activity.status),
                semantic_type=(
                    activity.semantic_type.value
                    if getattr(activity, "semantic_type", None) is not None
                    else None
                ),
                scope_type=activity.scope_type.value if activity.scope_type else None,
                observation_category=(
                    activity.observation_category.value if activity.observation_category else None
                ),
                observation_status=(
                    activity.observation_status.value if activity.observation_status else None
                ),
                observation_id=activity.observation_id,
                follow_up_of_id=activity.follow_up_of_id,
                plan_item_id=activity.plan_item_id,
            )
            for activity, activity_type in rows
        ]

    def _validate_scope(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        scope_type: PlanningScopeType,
        scope_id: UUID,
    ) -> None:
        if scope_type == PlanningScopeType.PARCEL:
            if scope_id != parcel_id:
                raise AppError("scope_id mora biti ID parcele za scope parcel.", status_code=422, code="invalid_scope")
            return
        if scope_type == PlanningScopeType.ROW:
            row = self.db.get(Row, scope_id)
            if row is None or row.parcel_id != parcel_id:
                raise NotFoundError("Red nije pronađen na parceli")
            return
        if scope_type == PlanningScopeType.TREE:
            tree = self.db.get(Tree, scope_id)
            if tree is None or tree.parcel_id != parcel_id:
                raise NotFoundError("Stablo nije pronađeno na parceli")
            return
        raise AppError("Nepoznat scope_type", status_code=422, code="invalid_scope")

    def _parcel(self, owner_id: UUID, parcel_id: UUID):
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel

    def _get_season(self, season_id: UUID, owner_id: UUID) -> PlanningSeason:
        season = self.seasons.get_for_owner(season_id, owner_id)
        if season is None:
            raise NotFoundError("Planerska sezona nije pronađena")
        return season

    def _get_plan(self, plan_id: UUID, owner_id: UUID) -> PlanningPlan:
        plan = self.plans.get_for_owner(plan_id, owner_id)
        if plan is None:
            raise NotFoundError("Plan nije pronađen")
        return plan


def _parcel_variety_names(parcel) -> list[str]:
    names: list[str] = []
    for item in parcel.varieties or []:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name and name not in names:
            names.append(name)
    if not names and parcel.default_variety:
        names.append(parcel.default_variety)
    return names


def _well_location_sr(value: str | None) -> str | None:
    if not value:
        return None
    return {
        "north": "sever",
        "northeast": "severoistok",
        "east": "istok",
        "southeast": "jugoistok",
        "south": "jug",
        "southwest": "jugozapad",
        "west": "zapad",
        "northwest": "severozapad",
    }.get(value, value)


def _irrigation_type_sr(value: str | None) -> str | None:
    if not value:
        return None
    return {
        "drip": "kap po kap",
        "sprinkler": "prskalice",
        "microsprinkler": "mikroprskalice",
        "other": "drugo",
    }.get(value, value)
