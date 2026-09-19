from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.farm import FarmDetail, FarmRead
from app.services.farm import FarmService

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=list[FarmRead])
def list_farms(current_user: CurrentUser, db: DBSession) -> list[FarmRead]:
    farms = FarmService(db).list_for_user(current_user.id)
    return [FarmRead.model_validate(farm) for farm in farms]


@router.get("/{farm_id}", response_model=FarmDetail)
def get_farm(farm_id: UUID, current_user: CurrentUser, db: DBSession) -> FarmDetail:
    farm = FarmService(db).get_for_user(farm_id, current_user.id)
    return FarmDetail.model_validate(farm)
