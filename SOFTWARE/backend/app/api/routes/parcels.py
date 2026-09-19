from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.journal import TreeJournalRead, TreeOptionRead
from app.schemas.orchard import OrchardTwinRead, RowRead, TreeDetailRead
from app.schemas.parcel import ParcelCreate, ParcelRead, ParcelUpdate
from app.schemas.report import ParcelAnnualReportRead
from app.services.journal import JournalService
from app.services.orchard import OrchardService
from app.services.parcel_report import ParcelReportService

router = APIRouter(prefix="/parcels", tags=["parcels"])


@router.get("", response_model=list[ParcelRead])
def list_parcels(current_user: CurrentUser, db: DBSession) -> list[ParcelRead]:
    return OrchardService(db).list_parcels(current_user.id)


@router.post("", response_model=ParcelRead, status_code=201)
def create_parcel(payload: ParcelCreate, current_user: CurrentUser, db: DBSession) -> ParcelRead:
    service = OrchardService(db)
    parcel = service.create_parcel(current_user.id, payload)
    return service.to_parcel_read(parcel)


@router.get("/{parcel_id}/report", response_model=ParcelAnnualReportRead)
def get_parcel_annual_report(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None, ge=1990, le=2100),
) -> ParcelAnnualReportRead:
    return ParcelReportService(db).get_parcel_annual_report(
        current_user.id,
        parcel_id,
        year or date.today().year,
    )


@router.get("/{parcel_id}", response_model=ParcelRead)
def get_parcel(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> ParcelRead:
    service = OrchardService(db)
    parcel = service.get_parcel(parcel_id, current_user.id)
    return service.to_parcel_read(parcel)


@router.patch("/{parcel_id}", response_model=ParcelRead)
def update_parcel(parcel_id: UUID, payload: ParcelUpdate, current_user: CurrentUser, db: DBSession) -> ParcelRead:
    service = OrchardService(db)
    parcel = service.update_parcel(parcel_id, current_user.id, payload)
    return service.to_parcel_read(parcel)


@router.delete("/{parcel_id}", status_code=204)
def delete_parcel(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    OrchardService(db).delete_parcel(parcel_id, current_user.id)


@router.get("/{parcel_id}/twin", response_model=OrchardTwinRead)
def get_orchard_twin(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> OrchardTwinRead:
    return OrchardService(db).get_twin(parcel_id, current_user.id)


@router.get("/{parcel_id}/rows", response_model=list[RowRead])
def list_parcel_rows(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> list[RowRead]:
    return OrchardService(db).list_rows(parcel_id, current_user.id)


@router.get("/{parcel_id}/trees", response_model=list[TreeOptionRead])
def list_parcel_trees(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    row_id: UUID | None = None,
) -> list[TreeOptionRead]:
    return OrchardService(db).list_tree_options(parcel_id, current_user.id, row_id)


@router.get("/{parcel_id}/trees/{tree_id}", response_model=TreeDetailRead)
def get_tree_detail(
    parcel_id: UUID,
    tree_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> TreeDetailRead:
    return OrchardService(db).get_tree_detail(parcel_id, tree_id, current_user.id)


@router.get("/{parcel_id}/trees/{tree_id}/journal", response_model=TreeJournalRead)
def get_tree_journal(
    parcel_id: UUID,
    tree_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> TreeJournalRead:
    return JournalService(db).get_tree_journal(parcel_id, tree_id, current_user.id)
