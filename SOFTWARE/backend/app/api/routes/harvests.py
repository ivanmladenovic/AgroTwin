from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession
from app.schemas.harvest import HarvestEventCreate, HarvestEventRead, HarvestEventUpdate, ParcelProductionRead
from app.services.harvest import HarvestService

router = APIRouter(tags=["harvests"])


@router.get("/parcels/{parcel_id}/production", response_model=ParcelProductionRead)
def get_parcel_production(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None, ge=1990, le=2100),
) -> ParcelProductionRead:
    return HarvestService(db).get_production(current_user.id, parcel_id, year or date.today().year)


@router.get("/parcels/{parcel_id}/harvests/export.csv")
def export_parcel_harvests(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None, ge=1990, le=2100),
) -> StreamingResponse:
    content = HarvestService(db).harvests_csv(current_user.id, parcel_id, year or date.today().year)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=production-{year or date.today().year}.csv"},
    )


@router.get("/parcels/{parcel_id}/harvests", response_model=list[HarvestEventRead])
def list_parcel_harvests(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None, ge=1990, le=2100),
) -> list[HarvestEventRead]:
    return HarvestService(db).list_harvests(current_user.id, parcel_id, year or date.today().year)


@router.post("/parcels/{parcel_id}/harvests", response_model=HarvestEventRead, status_code=201)
def create_parcel_harvest(
    parcel_id: UUID,
    payload: HarvestEventCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> HarvestEventRead:
    service = HarvestService(db)
    event = service.create_harvest(current_user.id, parcel_id, payload, current_user.id)
    return service.to_harvest_read(event, include_photos=True)


@router.get("/parcels/{parcel_id}/harvests/{harvest_id}", response_model=HarvestEventRead)
def get_parcel_harvest(
    parcel_id: UUID,
    harvest_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> HarvestEventRead:
    return HarvestService(db).get_harvest(current_user.id, parcel_id, harvest_id)


@router.patch("/parcels/{parcel_id}/harvests/{harvest_id}", response_model=HarvestEventRead)
def update_parcel_harvest(
    parcel_id: UUID,
    harvest_id: UUID,
    payload: HarvestEventUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> HarvestEventRead:
    service = HarvestService(db)
    event = service.update_harvest(current_user.id, parcel_id, harvest_id, payload)
    return service.to_harvest_read(event, include_photos=True)


@router.delete("/parcels/{parcel_id}/harvests/{harvest_id}", status_code=204)
def delete_parcel_harvest(
    parcel_id: UUID,
    harvest_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    HarvestService(db).delete_harvest(current_user.id, parcel_id, harvest_id)
