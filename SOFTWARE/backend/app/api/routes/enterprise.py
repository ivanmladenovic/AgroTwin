from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import MessageResponse
from app.schemas.enterprise import (
    ChangePasswordRequest,
    EnterpriseAggregateReport,
    EnterpriseAggregateReportRequest,
    EnterpriseAlertReviewRead,
    EnterpriseAlertReviewRequest,
    EnterpriseAlertWatchPage,
    EnterpriseAssignableParcel,
    EnterpriseDashboardKPIs,
    EnterpriseDataQuality,
    EnterpriseFollowUpCreate,
    EnterpriseFollowUpRead,
    EnterpriseFollowUpUpdate,
    EnterpriseFarmCandidate,
    EnterpriseMapParcel,
    EnterpriseMembershipCreate,
    EnterpriseMembershipRead,
    EnterpriseMembershipUpdate,
    EnterpriseMeResponse,
    EnterpriseMonitoringCenter,
    EnterpriseOtkupOverview,
    EnterpriseOrganizationRead,
    EnterprisePurchaseCreate,
    EnterprisePurchaseRead,
    EnterprisePurchaseUpdate,
    EnterpriseSupplierPriceRead,
    EnterpriseSupplierPriceUpsert,
    EnterpriseOrganizationUpdate,
    EnterpriseParcelAssignmentCreate,
    EnterpriseParcelAssignmentRead,
    EnterpriseParcelAssignmentUpdate,
    EnterpriseParcelDetail,
    EnterpriseParcelSummary,
    EnterprisePlanningSeasonCreate,
    EnterprisePlanningSeasonRead,
    EnterprisePlanningSeasonUpdate,
    EnterpriseProductionAnalytics,
    EnterpriseSupplierLinkCreate,
    EnterpriseSupplierLinkRead,
    EnterpriseSupplierLinkUpdate,
    EnterpriseYieldComparison,
    EnterpriseYieldPlanCreate,
    EnterpriseYieldPlanRead,
)
from app.schemas.orchard import OrchardTwinRead
from app.schemas.satellite import SatelliteHistoryRead
from app.schemas.user import UserRead
from app.services.enterprise import EnterpriseService
from app.services.enterprise_alerts import EnterpriseAlertWatchService
from app.services.enterprise_data_quality import EnterpriseDataQualityService
from app.services.enterprise_followups import EnterpriseFollowUpService
from app.services.enterprise_otkup import EnterpriseOtkupService

router = APIRouter(prefix="/enterprise", tags=["enterprise"])


@router.get("/me", response_model=EnterpriseMeResponse)
def enterprise_me(current_user: CurrentUser, db: DBSession) -> EnterpriseMeResponse:
    return EnterpriseService(db).me(current_user)


@router.post("/change-password", response_model=UserRead)
def change_password(
    payload: ChangePasswordRequest, current_user: CurrentUser, db: DBSession
) -> UserRead:
    user = EnterpriseService(db).change_password(
        current_user, payload.current_password, payload.new_password
    )
    db.commit()
    return UserRead.model_validate(user)


@router.get("/organizations/{organization_id}", response_model=EnterpriseOrganizationRead)
def get_organization(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> EnterpriseOrganizationRead:
    return EnterpriseService(db).get_organization(current_user, organization_id)


@router.patch("/organizations/{organization_id}", response_model=EnterpriseOrganizationRead)
def update_organization(
    organization_id: UUID,
    payload: EnterpriseOrganizationUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseOrganizationRead:
    result = EnterpriseService(db).update_organization(current_user, organization_id, payload)
    db.commit()
    return result


@router.get("/organizations/{organization_id}/dashboard", response_model=EnterpriseDashboardKPIs)
def dashboard(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None),
) -> EnterpriseDashboardKPIs:
    return EnterpriseService(db).dashboard(current_user, organization_id, year=year)


@router.get(
    "/organizations/{organization_id}/data-quality",
    response_model=EnterpriseDataQuality,
)
def data_quality(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None),
    bucket: str | None = Query(default=None),
) -> EnterpriseDataQuality:
    return EnterpriseDataQualityService(db).summary(
        current_user, organization_id, year=year, bucket=bucket
    )


@router.get(
    "/organizations/{organization_id}/map-parcels",
    response_model=list[EnterpriseMapParcel],
)
def map_parcels(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[EnterpriseMapParcel]:
    return EnterpriseService(db).map_parcels(current_user, organization_id)


@router.get(
    "/organizations/{organization_id}/monitoring",
    response_model=EnterpriseMonitoringCenter,
)
def monitoring_center(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None),
    farm_id: UUID | None = Query(default=None),
    parcel_id: UUID | None = Query(default=None),
    category: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> EnterpriseMonitoringCenter:
    return EnterpriseService(db).monitoring_center(
        current_user,
        organization_id,
        year=year,
        farm_id=farm_id,
        parcel_id=parcel_id,
        category=category,
        review_status=review_status,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/organizations/{organization_id}/production-analytics",
    response_model=EnterpriseProductionAnalytics,
)
def production_analytics(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    years_back: int = Query(default=5, ge=1, le=15),
    year: int | None = Query(default=None),
    parcel_ids: list[UUID] | None = Query(default=None),
) -> EnterpriseProductionAnalytics:
    return EnterpriseService(db).production_analytics(
        current_user,
        organization_id,
        years_back=years_back,
        reference_year=year,
        parcel_ids=parcel_ids,
    )


@router.post(
    "/organizations/{organization_id}/reports/aggregate",
    response_model=EnterpriseAggregateReport,
)
def aggregate_report(
    organization_id: UUID,
    payload: EnterpriseAggregateReportRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseAggregateReport:
    return EnterpriseService(db).aggregate_report(
        current_user,
        organization_id,
        parcel_ids=payload.parcel_ids,
        year=payload.year,
    )


@router.get(
    "/organizations/{organization_id}/memberships",
    response_model=list[EnterpriseMembershipRead],
)
def list_memberships(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[EnterpriseMembershipRead]:
    return EnterpriseService(db).list_memberships(current_user, organization_id)


@router.post(
    "/organizations/{organization_id}/memberships",
    response_model=EnterpriseMembershipRead,
    status_code=201,
)
def add_membership(
    organization_id: UUID,
    payload: EnterpriseMembershipCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseMembershipRead:
    result = EnterpriseService(db).add_membership(current_user, organization_id, payload)
    db.commit()
    return result


@router.patch(
    "/organizations/{organization_id}/memberships/{membership_id}",
    response_model=EnterpriseMembershipRead,
)
def update_membership(
    organization_id: UUID,
    membership_id: UUID,
    payload: EnterpriseMembershipUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseMembershipRead:
    result = EnterpriseService(db).update_membership(
        current_user, organization_id, membership_id, payload
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/follow-ups",
    response_model=list[EnterpriseFollowUpRead],
)
def list_follow_ups(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    status: str | None = Query(default=None),
    farm_id: UUID | None = Query(default=None),
    parcel_id: UUID | None = Query(default=None),
    assignee_user_id: UUID | None = Query(default=None),
    due: str | None = Query(default=None),
    upcoming_days: int = Query(default=7, ge=1, le=30),
) -> list[EnterpriseFollowUpRead]:
    return EnterpriseFollowUpService(db).list_tasks(
        current_user,
        organization_id,
        status=status,
        farm_id=farm_id,
        parcel_id=parcel_id,
        assignee_user_id=assignee_user_id,
        due=due,
        upcoming_days=upcoming_days,
    )


@router.post(
    "/organizations/{organization_id}/follow-ups",
    response_model=EnterpriseFollowUpRead,
    status_code=201,
)
def create_follow_up(
    organization_id: UUID,
    payload: EnterpriseFollowUpCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseFollowUpRead:
    result = EnterpriseFollowUpService(db).create_task(current_user, organization_id, payload)
    db.commit()
    return result


@router.patch(
    "/organizations/{organization_id}/follow-ups/{task_id}",
    response_model=EnterpriseFollowUpRead,
)
def update_follow_up(
    organization_id: UUID,
    task_id: UUID,
    payload: EnterpriseFollowUpUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseFollowUpRead:
    result = EnterpriseFollowUpService(db).update_task(
        current_user, organization_id, task_id, payload
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/suppliers",
    response_model=list[EnterpriseSupplierLinkRead],
)
def list_suppliers(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    status: str | None = None,
    q: str | None = None,
) -> list[EnterpriseSupplierLinkRead]:
    return EnterpriseService(db).list_suppliers(
        current_user, organization_id, status=status, q=q
    )


@router.get(
    "/organizations/{organization_id}/suppliers/{link_id}",
    response_model=EnterpriseSupplierLinkRead,
)
def get_supplier(
    organization_id: UUID, link_id: UUID, current_user: CurrentUser, db: DBSession
) -> EnterpriseSupplierLinkRead:
    return EnterpriseService(db).get_supplier(current_user, organization_id, link_id)


@router.post(
    "/organizations/{organization_id}/suppliers",
    response_model=EnterpriseSupplierLinkRead,
    status_code=201,
)
def create_supplier(
    organization_id: UUID,
    payload: EnterpriseSupplierLinkCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseSupplierLinkRead:
    result = EnterpriseService(db).create_supplier(current_user, organization_id, payload)
    db.commit()
    return result


@router.patch(
    "/organizations/{organization_id}/suppliers/{link_id}",
    response_model=EnterpriseSupplierLinkRead,
)
def update_supplier(
    organization_id: UUID,
    link_id: UUID,
    payload: EnterpriseSupplierLinkUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseSupplierLinkRead:
    result = EnterpriseService(db).update_supplier(
        current_user, organization_id, link_id, payload
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/assignments",
    response_model=list[EnterpriseParcelAssignmentRead],
)
def list_assignments(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[EnterpriseParcelAssignmentRead]:
    return EnterpriseService(db).list_assignments(current_user, organization_id)


@router.post(
    "/organizations/{organization_id}/assignments",
    response_model=EnterpriseParcelAssignmentRead,
    status_code=201,
)
def assign_parcel(
    organization_id: UUID,
    payload: EnterpriseParcelAssignmentCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseParcelAssignmentRead:
    result = EnterpriseService(db).assign_parcel(current_user, organization_id, payload)
    db.commit()
    return result


@router.patch(
    "/organizations/{organization_id}/assignments/{assignment_id}",
    response_model=EnterpriseParcelAssignmentRead,
)
def update_assignment(
    organization_id: UUID,
    assignment_id: UUID,
    payload: EnterpriseParcelAssignmentUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseParcelAssignmentRead:
    result = EnterpriseService(db).update_assignment(
        current_user, organization_id, assignment_id, payload
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/parcels",
    response_model=list[EnterpriseParcelSummary],
)
def list_parcels(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    farm_id: UUID | None = None,
    q: str | None = None,
) -> list[EnterpriseParcelSummary]:
    return EnterpriseService(db).list_parcels(
        current_user, organization_id, farm_id=farm_id, q=q
    )


@router.get(
    "/organizations/{organization_id}/parcels/{parcel_id}",
    response_model=EnterpriseParcelDetail,
)
def get_parcel(
    organization_id: UUID, parcel_id: UUID, current_user: CurrentUser, db: DBSession
) -> EnterpriseParcelDetail:
    return EnterpriseService(db).get_parcel_detail(current_user, organization_id, parcel_id)


@router.get(
    "/organizations/{organization_id}/seasons",
    response_model=list[EnterprisePlanningSeasonRead],
)
def list_seasons(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[EnterprisePlanningSeasonRead]:
    return EnterpriseService(db).list_seasons(current_user, organization_id)


@router.post(
    "/organizations/{organization_id}/seasons",
    response_model=EnterprisePlanningSeasonRead,
    status_code=201,
)
def create_season(
    organization_id: UUID,
    payload: EnterprisePlanningSeasonCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterprisePlanningSeasonRead:
    result = EnterpriseService(db).create_season(current_user, organization_id, payload)
    db.commit()
    return result


@router.patch(
    "/organizations/{organization_id}/seasons/{season_id}",
    response_model=EnterprisePlanningSeasonRead,
)
def update_season(
    organization_id: UUID,
    season_id: UUID,
    payload: EnterprisePlanningSeasonUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterprisePlanningSeasonRead:
    result = EnterpriseService(db).update_season(
        current_user, organization_id, season_id, payload
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/yield-plans",
    response_model=list[EnterpriseYieldPlanRead],
)
def list_yield_plans(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    season_id: UUID | None = None,
) -> list[EnterpriseYieldPlanRead]:
    return EnterpriseService(db).list_yield_plans(current_user, organization_id, season_id)


@router.get(
    "/organizations/{organization_id}/yield-plans/{plan_id}",
    response_model=EnterpriseYieldPlanRead,
)
def get_yield_plan(
    organization_id: UUID, plan_id: UUID, current_user: CurrentUser, db: DBSession
) -> EnterpriseYieldPlanRead:
    return EnterpriseService(db).get_yield_plan(current_user, organization_id, plan_id)


@router.post(
    "/organizations/{organization_id}/yield-plans",
    response_model=EnterpriseYieldPlanRead,
    status_code=201,
)
def create_yield_plan(
    organization_id: UUID,
    payload: EnterpriseYieldPlanCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseYieldPlanRead:
    result = EnterpriseService(db).create_yield_plan(current_user, organization_id, payload)
    db.commit()
    return result


@router.post(
    "/organizations/{organization_id}/yield-plans/{plan_id}/recalculate",
    response_model=EnterpriseYieldPlanRead,
    status_code=201,
)
def recalculate_yield_plan(
    organization_id: UUID, plan_id: UUID, current_user: CurrentUser, db: DBSession
) -> EnterpriseYieldPlanRead:
    result = EnterpriseService(db).recalculate_yield_plan(
        current_user, organization_id, plan_id
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/yield-plans/{plan_id}/compare",
    response_model=EnterpriseYieldComparison,
)
def compare_yield_plan(
    organization_id: UUID, plan_id: UUID, current_user: CurrentUser, db: DBSession
) -> EnterpriseYieldComparison:
    return EnterpriseService(db).compare_yield_plan(current_user, organization_id, plan_id)


@router.get(
    "/organizations/{organization_id}/farms/linkable",
    response_model=list[EnterpriseFarmCandidate],
)
def list_linkable_farms(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    q: str | None = None,
) -> list[EnterpriseFarmCandidate]:
    return EnterpriseService(db).list_linkable_farms(current_user, organization_id, q=q)


@router.get(
    "/organizations/{organization_id}/farms/{farm_id}/assignable-parcels",
    response_model=list[EnterpriseAssignableParcel],
)
def list_assignable_parcels(
    organization_id: UUID, farm_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[EnterpriseAssignableParcel]:
    return EnterpriseService(db).list_assignable_parcels(
        current_user, organization_id, farm_id
    )


@router.get(
    "/organizations/{organization_id}/parcels/{parcel_id}/satellite/history",
    response_model=SatelliteHistoryRead,
)
def enterprise_parcel_satellite_history(
    organization_id: UUID,
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> SatelliteHistoryRead:
    """Read the producer's stored satellite history. Does not start a new sync."""
    return EnterpriseService(db).satellite_history(
        current_user,
        organization_id,
        parcel_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/organizations/{organization_id}/intelligence-alerts",
    response_model=EnterpriseAlertWatchPage,
)
def list_intelligence_alerts(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    farm_id: UUID | None = Query(default=None),
    parcel_id: UUID | None = Query(default=None),
    index: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    alert_status: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EnterpriseAlertWatchPage:
    """Existing producer alerts on parcels this organization can read. Does not run AI."""
    return EnterpriseAlertWatchService(db).list_alerts(
        current_user,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        farm_id=farm_id,
        parcel_id=parcel_id,
        index=index,
        severity=severity,
        alert_status=alert_status,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/organizations/{organization_id}/intelligence-alerts/{alert_id}/review",
    response_model=EnterpriseAlertReviewRead,
)
def review_intelligence_alert(
    organization_id: UUID,
    alert_id: UUID,
    payload: EnterpriseAlertReviewRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseAlertReviewRead:
    result = EnterpriseAlertWatchService(db).mark_reviewed(
        current_user,
        organization_id,
        alert_id,
        note=payload.note,
    )
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/parcels/{parcel_id}/twin",
    response_model=OrchardTwinRead,
)
def get_parcel_twin(
    organization_id: UUID, parcel_id: UUID, current_user: CurrentUser, db: DBSession
) -> OrchardTwinRead:
    return EnterpriseService(db).get_parcel_twin(current_user, organization_id, parcel_id)


@router.get(
    "/organizations/{organization_id}/otkup",
    response_model=EnterpriseOtkupOverview,
)
def otkup_overview(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None),
) -> EnterpriseOtkupOverview:
    return EnterpriseOtkupService(db).overview(current_user, organization_id, season_year=year)


@router.put(
    "/organizations/{organization_id}/otkup/prices",
    response_model=EnterpriseSupplierPriceRead,
)
def upsert_otkup_price(
    organization_id: UUID,
    payload: EnterpriseSupplierPriceUpsert,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterpriseSupplierPriceRead:
    result = EnterpriseOtkupService(db).upsert_price(current_user, organization_id, payload)
    db.commit()
    return result


@router.get(
    "/organizations/{organization_id}/otkup/purchases",
    response_model=list[EnterprisePurchaseRead],
)
def list_otkup_purchases(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None),
    farm_id: UUID | None = Query(default=None),
) -> list[EnterprisePurchaseRead]:
    return EnterpriseOtkupService(db).list_purchases(
        current_user, organization_id, season_year=year, farm_id=farm_id
    )


@router.post(
    "/organizations/{organization_id}/otkup/purchases",
    response_model=EnterprisePurchaseRead,
    status_code=201,
)
def create_otkup_purchase(
    organization_id: UUID,
    payload: EnterprisePurchaseCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterprisePurchaseRead:
    result = EnterpriseOtkupService(db).create_purchase(current_user, organization_id, payload)
    db.commit()
    return result


@router.patch(
    "/organizations/{organization_id}/otkup/purchases/{purchase_id}",
    response_model=EnterprisePurchaseRead,
)
def update_otkup_purchase(
    organization_id: UUID,
    purchase_id: UUID,
    payload: EnterprisePurchaseUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> EnterprisePurchaseRead:
    result = EnterpriseOtkupService(db).update_purchase(
        current_user, organization_id, purchase_id, payload
    )
    db.commit()
    return result


@router.delete(
    "/organizations/{organization_id}/otkup/purchases/{purchase_id}",
    response_model=MessageResponse,
)
def delete_otkup_purchase(
    organization_id: UUID,
    purchase_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> MessageResponse:
    EnterpriseOtkupService(db).delete_purchase(current_user, organization_id, purchase_id)
    db.commit()
    return MessageResponse(detail="Otkup obrisan")


@router.get("/organizations/{organization_id}/exports/parcels.csv")
def export_parcels_csv(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> PlainTextResponse:
    content = EnterpriseService(db).export_parcels_csv(current_user, organization_id)
    db.commit()
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="enterprise-parcels.csv"',
        },
    )


@router.get("/organizations/{organization_id}/exports/intelligence-alerts.csv")
def export_intelligence_alerts_csv(
    organization_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    farm_id: UUID | None = Query(default=None),
    parcel_id: UUID | None = Query(default=None),
    index: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    alert_status: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
) -> PlainTextResponse:
    content = EnterpriseAlertWatchService(db).export_csv(
        current_user,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        farm_id=farm_id,
        parcel_id=parcel_id,
        index=index,
        severity=severity,
        alert_status=alert_status,
        review_status=review_status,
    )
    db.commit()
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="enterprise-alerts.csv"',
        },
    )


@router.get("/organizations/{organization_id}/exports/yield-plans/{plan_id}.csv")
def export_yield_plan_csv(
    organization_id: UUID, plan_id: UUID, current_user: CurrentUser, db: DBSession
) -> PlainTextResponse:
    content = EnterpriseService(db).export_yield_plan_csv(
        current_user, organization_id, plan_id
    )
    db.commit()
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="enterprise-plan-{plan_id}.csv"',
        },
    )


@router.post(
    "/organizations/{organization_id}/producer-write-guard",
    response_model=MessageResponse,
    include_in_schema=False,
)
def producer_write_guard(
    organization_id: UUID, current_user: CurrentUser, db: DBSession
) -> MessageResponse:
    """Testable endpoint proving Enterprise cannot mutate producer operational data via this API."""
    EnterpriseService(db).access.require_reader(current_user, organization_id)
    EnterpriseService(db).access.deny_producer_write()
    return MessageResponse(detail="unreachable")
