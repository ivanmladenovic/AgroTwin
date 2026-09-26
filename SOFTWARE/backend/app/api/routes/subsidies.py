from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.subsidy import SubsidyCreate, SubsidyRead, SubsidyUpdate
from app.services.subsidy import SubsidyService

router = APIRouter(prefix="/subsidies", tags=["subsidies"])


@router.get("", response_model=list[SubsidyRead])
def list_subsidies(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
) -> list[SubsidyRead]:
    return SubsidyService(db).list_subsidies(current_user.id, parcel_id)


@router.post("", response_model=SubsidyRead, status_code=201)
def create_subsidy(payload: SubsidyCreate, current_user: CurrentUser, db: DBSession) -> SubsidyRead:
    service = SubsidyService(db)
    subsidy = service.create(current_user.id, payload, current_user.id)
    return service.to_read(subsidy)


@router.patch("/{subsidy_id}", response_model=SubsidyRead)
def update_subsidy(
    subsidy_id: UUID,
    payload: SubsidyUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> SubsidyRead:
    service = SubsidyService(db)
    subsidy = service.update(subsidy_id, current_user.id, payload)
    return service.to_read(subsidy)


@router.delete("/{subsidy_id}", status_code=204)
def delete_subsidy(subsidy_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    SubsidyService(db).delete(subsidy_id, current_user.id)
