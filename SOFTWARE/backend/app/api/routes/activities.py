from datetime import date
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession
from app.models.enums import ActivityStatus, ScopeType
from app.schemas.activity import ActivityCreate, ActivityRead, ActivityUpdate
from app.schemas.cost import CostCreate, CostItemRead
from app.services.activity import ActivityService
from app.services.export import ExportService

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("", response_model=list[ActivityRead])
def list_activities(
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = None,
    date_to: date | None = None,
    activity_type_id: UUID | None = None,
    scope_type: ScopeType | None = None,
    parcel_id: UUID | None = None,
    row_id: UUID | None = None,
    tree_id: UUID | None = None,
    status: ActivityStatus | None = None,
) -> list[ActivityRead]:
    return ActivityService(db).list_activities(
        current_user.id,
        date_from=date_from,
        date_to=date_to,
        activity_type_id=activity_type_id,
        scope_type=scope_type,
        parcel_id=parcel_id,
        row_id=row_id,
        tree_id=tree_id,
        status=status,
    )


@router.get("/export.csv")
def export_activities(
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = None,
    date_to: date | None = None,
    parcel_id: UUID | None = None,
) -> StreamingResponse:
    content = ExportService(db).activities_csv(
        current_user.id, date_from=date_from, date_to=date_to, parcel_id=parcel_id
    )
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activities.csv"},
    )


@router.post("", response_model=ActivityRead, status_code=201)
def create_activity(payload: ActivityCreate, current_user: CurrentUser, db: DBSession) -> ActivityRead:
    service = ActivityService(db)
    activity = service.create_activity(current_user.id, payload, current_user.id)
    return service.to_activity_read(activity)


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: UUID, current_user: CurrentUser, db: DBSession) -> ActivityRead:
    service = ActivityService(db)
    return service.to_activity_read(service.get_activity(activity_id, current_user.id))


@router.patch("/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: UUID,
    payload: ActivityUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> ActivityRead:
    service = ActivityService(db)
    activity = service.update_activity(activity_id, current_user.id, payload)
    return service.to_activity_read(activity)


@router.post("/{activity_id}/costs", response_model=CostItemRead, status_code=201)
def add_activity_cost(
    activity_id: UUID,
    payload: CostCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> CostItemRead:
    service = ActivityService(db)
    cost = service.add_cost(activity_id, current_user.id, payload, current_user.id)
    return service.to_cost_read(cost)
