from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.planning import (
    ExpertReviewDecisionRequest,
    ExpertReviewSubmitRequest,
    IrrigationPlanGenerateRequest,
    NutritionPlanGenerateRequest,
    PlanningCopyRequest,
    PlanningDashboard,
    PlanningParcelSummary,
    PlanningPlanCreate,
    PlanningPlanItemCreate,
    PlanningPlanItemRead,
    PlanningPlanItemUpdate,
    PlanningPlanRead,
    PlanningSeasonCreate,
    PlanningSeasonRead,
    PlanningSeasonUpdate,
    ProtectionPlanGenerateRequest,
)
from app.services.planning import PlanningService

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/parcels/{parcel_id}/summary", response_model=PlanningParcelSummary)
def parcel_planning_summary(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningParcelSummary:
    return PlanningService(db).parcel_summary(current_user.id, parcel_id)


@router.get("/parcels/{parcel_id}/dashboard", response_model=PlanningDashboard)
def parcel_planning_dashboard(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int = Query(..., ge=1990, le=2100),
) -> PlanningDashboard:
    return PlanningService(db).dashboard(current_user.id, parcel_id, year)


@router.get("/parcels/{parcel_id}/seasons", response_model=list[PlanningSeasonRead])
def list_planning_seasons(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[PlanningSeasonRead]:
    return PlanningService(db).list_seasons(current_user.id, parcel_id)


@router.post("/parcels/{parcel_id}/seasons", response_model=PlanningSeasonRead, status_code=201)
def create_planning_season(
    parcel_id: UUID,
    payload: PlanningSeasonCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningSeasonRead:
    service = PlanningService(db)
    season = service.create_season(current_user.id, parcel_id, payload, current_user.id)
    return service.to_season_read(season, include_plans=True)


@router.get("/seasons/{season_id}", response_model=PlanningSeasonRead)
def get_planning_season(
    season_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningSeasonRead:
    return PlanningService(db).get_season(season_id, current_user.id)


@router.patch("/seasons/{season_id}", response_model=PlanningSeasonRead)
def update_planning_season(
    season_id: UUID,
    payload: PlanningSeasonUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningSeasonRead:
    service = PlanningService(db)
    season = service.update_season(season_id, current_user.id, payload)
    return service.to_season_read(season, include_plans=True)


@router.post("/seasons/{season_id}/finish", response_model=PlanningSeasonRead)
def finish_planning_season(
    season_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningSeasonRead:
    service = PlanningService(db)
    season = service.finish_season(season_id, current_user.id)
    return service.to_season_read(season, include_plans=True)


@router.post("/seasons/{season_id}/copy-from", response_model=PlanningSeasonRead)
def copy_planning_season(
    season_id: UUID,
    payload: PlanningCopyRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningSeasonRead:
    service = PlanningService(db)
    season = service.copy_from_season(season_id, current_user.id, payload)
    return service.to_season_read(season, include_plans=True)


@router.get("/seasons/{season_id}/plans", response_model=list[PlanningPlanRead])
def list_planning_plans(
    season_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[PlanningPlanRead]:
    return PlanningService(db).list_plans(season_id, current_user.id)


@router.post("/seasons/{season_id}/plans", response_model=PlanningPlanRead, status_code=201)
def create_planning_plan(
    season_id: UUID,
    payload: PlanningPlanCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningPlanRead:
    service = PlanningService(db)
    plan = service.create_plan(season_id, current_user.id, payload)
    return service.to_plan_read(plan, include_items=True)


@router.get("/plans/{plan_id}", response_model=PlanningPlanRead)
def get_planning_plan(
    plan_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningPlanRead:
    return PlanningService(db).get_plan(plan_id, current_user.id)


@router.post("/seasons/{season_id}/plans/protection/generate", response_model=PlanningPlanRead)
def generate_protection_plan(
    season_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    payload: ProtectionPlanGenerateRequest | None = None,
) -> PlanningPlanRead:
    return PlanningService(db).generate_protection_plan(
        season_id,
        current_user.id,
        payload or ProtectionPlanGenerateRequest(),
    )


@router.post("/seasons/{season_id}/plans/nutrition/generate", response_model=PlanningPlanRead)
def generate_nutrition_plan(
    season_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    payload: NutritionPlanGenerateRequest | None = None,
) -> PlanningPlanRead:
    return PlanningService(db).generate_nutrition_plan(
        season_id,
        current_user.id,
        payload or NutritionPlanGenerateRequest(),
    )


@router.post("/seasons/{season_id}/plans/irrigation/generate", response_model=PlanningPlanRead)
def generate_irrigation_plan(
    season_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    payload: IrrigationPlanGenerateRequest | None = None,
) -> PlanningPlanRead:
    return PlanningService(db).generate_irrigation_plan(
        season_id,
        current_user.id,
        payload or IrrigationPlanGenerateRequest(),
    )


@router.post("/plans/{plan_id}/items", response_model=PlanningPlanItemRead, status_code=201)
def create_planning_plan_item(
    plan_id: UUID,
    payload: PlanningPlanItemCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningPlanItemRead:
    service = PlanningService(db)
    item = service.create_item(plan_id, current_user.id, payload)
    return service.to_item_read(item)


@router.patch("/plans/{plan_id}/items/{item_id}", response_model=PlanningPlanItemRead)
def update_planning_plan_item(
    plan_id: UUID,
    item_id: UUID,
    payload: PlanningPlanItemUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningPlanItemRead:
    service = PlanningService(db)
    item = service.update_item(plan_id, item_id, current_user.id, payload)
    return service.to_item_read(item)


@router.post(
    "/plans/{plan_id}/items/{item_id}/expert-review/submit",
    response_model=PlanningPlanItemRead,
)
def submit_expert_review(
    plan_id: UUID,
    item_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    payload: ExpertReviewSubmitRequest | None = None,
) -> PlanningPlanItemRead:
    return PlanningService(db).submit_expert_review(
        plan_id,
        item_id,
        current_user.id,
        current_user,
        payload,
    )


@router.post(
    "/plans/{plan_id}/items/{item_id}/expert-review/{review_id}/decide",
    response_model=PlanningPlanItemRead,
)
def decide_expert_review(
    plan_id: UUID,
    item_id: UUID,
    review_id: UUID,
    payload: ExpertReviewDecisionRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> PlanningPlanItemRead:
    return PlanningService(db).decide_expert_review(
        plan_id,
        item_id,
        review_id,
        current_user.id,
        current_user,
        payload,
    )
