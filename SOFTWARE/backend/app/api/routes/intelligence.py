from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.enterprise.access import EnterpriseAccess
from app.schemas.intelligence import (
    IntelligenceDashboardRead,
    ParcelAlertRead,
    ParcelAnalysisRunRead,
    UserNotificationRead,
)
from app.services.intelligence import IntelligenceService

router = APIRouter(tags=["intelligence"])


@router.get(
    "/parcels/{parcel_id}/intelligence",
    response_model=IntelligenceDashboardRead,
)
def get_parcel_intelligence(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> IntelligenceDashboardRead:
    service = IntelligenceService(db)
    try:
        return service.get_dashboard(current_user.id, parcel_id)
    except NotFoundError:
        if not EnterpriseAccess(db).user_can_read_parcel(current_user, parcel_id):
            raise
        return service.get_dashboard_readonly(parcel_id)


@router.post(
    "/parcels/{parcel_id}/intelligence/analyze",
    response_model=ParcelAnalysisRunRead,
)
def request_parcel_intelligence(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ParcelAnalysisRunRead:
    return IntelligenceService(db).request_manual_analysis(current_user.id, parcel_id)


@router.post(
    "/intelligence/alerts/{alert_id}/acknowledge",
    response_model=ParcelAlertRead,
)
def acknowledge_alert(
    alert_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ParcelAlertRead:
    return IntelligenceService(db).acknowledge_alert(current_user.id, alert_id)


@router.post(
    "/intelligence/alerts/{alert_id}/resolve",
    response_model=ParcelAlertRead,
)
def resolve_alert(
    alert_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ParcelAlertRead:
    return IntelligenceService(db).resolve_alert(current_user.id, alert_id)


@router.get("/notifications", response_model=list[UserNotificationRead])
def list_notifications(current_user: CurrentUser, db: DBSession) -> list[UserNotificationRead]:
    return IntelligenceService(db).list_notifications(current_user.id)
