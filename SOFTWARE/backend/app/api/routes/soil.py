from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.soil import ParcelSoilProfileRead
from app.services.soil import SoilService

router = APIRouter(tags=["soil"])


@router.get("/parcels/{parcel_id}/soil/profile", response_model=ParcelSoilProfileRead)
def get_parcel_soil_profile(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> ParcelSoilProfileRead:
    return SoilService(db).get_profile(current_user.id, parcel_id)


@router.post("/parcels/{parcel_id}/soil/refresh", response_model=ParcelSoilProfileRead)
def refresh_parcel_soil_profile(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> ParcelSoilProfileRead:
    return SoilService(db).refresh_profile(current_user.id, parcel_id)
