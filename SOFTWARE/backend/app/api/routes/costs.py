from datetime import date
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession
from app.schemas.cost import CostItemRead, CostSummaryRead
from app.services.activity import ActivityService
from app.services.export import ExportService

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("", response_model=list[CostItemRead])
def list_costs(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CostItemRead]:
    return ActivityService(db).list_costs(
        current_user.id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
    )


@router.get("/summary", response_model=CostSummaryRead)
def cost_summary(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
) -> CostSummaryRead:
    return ActivityService(db).cost_summary(current_user.id, parcel_id)


@router.get("/export.csv")
def export_costs(
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = None,
    date_to: date | None = None,
    parcel_id: UUID | None = None,
) -> StreamingResponse:
    content = ExportService(db).costs_csv(
        current_user.id, date_from=date_from, date_to=date_to, parcel_id=parcel_id
    )
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=costs.csv"},
    )
