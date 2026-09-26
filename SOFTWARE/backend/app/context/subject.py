"""Subject hierarchy resolution. Critical failures raise AppError."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.context.request import ContextRequest, ResolvedSubject
from app.context.types import SubjectType
from app.core.exceptions import AppError, NotFoundError
from app.models.enums import AttachmentEntityType
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.activity import ActivityRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.photo import PhotoRepository
from app.repositories.row import RowRepository


class SubjectResolver:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.photos = PhotoRepository(db)
        self.activities = ActivityRepository(db)
        self.diseases = DiseaseRepository(db)

    def resolve(self, owner_id: UUID, request: ContextRequest) -> ResolvedSubject:
        photo = None
        activity = None
        disease_case = None

        if request.photo_id is not None:
            photo = self.photos.get_for_owner(request.photo_id, owner_id)
            if photo is None:
                raise NotFoundError("Fotografija nije pronađena")

        activity_id = request.activity_id
        case_id = request.disease_case_id
        if photo is not None and activity_id is None and photo.entity_type == AttachmentEntityType.ACTIVITY:
            activity_id = photo.entity_id
        if photo is not None and case_id is None and photo.entity_type == AttachmentEntityType.DISEASE_CASE:
            case_id = photo.entity_id

        if activity_id is not None:
            activity = self.activities.get_for_owner(activity_id, owner_id)
            if activity is None:
                raise NotFoundError("Aktivnost nije pronađena")

        if case_id is not None:
            disease_case = self.diseases.get_for_owner(case_id, owner_id)
            if disease_case is None:
                raise NotFoundError("Prijava problema nije pronađena")

        parcel_id, row_id, tree_id = _ids_from_request(request, photo, activity, disease_case)
        if parcel_id is None and row_id is None and tree_id is None:
            raise AppError("Potreban je parcel_id, row_id, tree_id, photo_id, activity_id ili disease_case_id", 400)

        tree: Tree | None = None
        row: Row | None = None
        parcel: Parcel | None = None

        if tree_id is not None:
            tree = self.db.get(Tree, tree_id)
            if tree is None:
                raise NotFoundError("Stablo nije pronađeno")
            parcel = self.parcels.get_for_owner(tree.parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Stablo nije pronađeno")
            if parcel_id is not None and tree.parcel_id != parcel_id:
                raise AppError("Stablo ne pripada navedenoj parceli", 400)
            if row_id is not None and tree.row_id != row_id:
                raise AppError("Stablo ne pripada navedenom redu", 400)
            row = self.rows.get_for_parcel(parcel.id, tree.row_id)
            if row is None:
                raise NotFoundError("Red nije pronađen")
        elif row_id is not None:
            row = self.rows.get_by_id(row_id)
            if row is None:
                raise NotFoundError("Red nije pronađen")
            parcel = self.parcels.get_for_owner(row.parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Red nije pronađen")
            if parcel_id is not None and row.parcel_id != parcel_id:
                raise AppError("Red ne pripada navedenoj parceli", 400)
        elif parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
            if request.row_id is not None:
                raise AppError("Red ne pripada navedenoj parceli", 400)
            if request.tree_id is not None:
                raise AppError("Stablo ne pripada navedenoj parceli", 400)

        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        farm = parcel.farm if parcel.farm is not None else self.farms.get_by_id_for_owner(parcel.farm_id, owner_id)
        if farm is None or farm.owner_id != owner_id:
            raise NotFoundError("Parcela nije pronađena")

        event_date, event_at = _event_date(request, photo, activity, disease_case)
        season_year = request.season_year or event_date.year
        subject_type = SubjectType.TREE.value if tree is not None else SubjectType.ROW.value if row is not None else SubjectType.PARCEL.value
        return ResolvedSubject(
            type=subject_type,
            farm=farm,
            parcel=parcel,
            row=row,
            tree=tree,
            photo=photo,
            activity=activity,
            disease_case=disease_case,
            event_date=event_date,
            event_at=event_at,
            season_year=season_year,
        )


def _ids_from_request(
    request: ContextRequest,
    photo,
    activity,
    disease_case,
) -> tuple[UUID | None, UUID | None, UUID | None]:
    parcel_id = request.parcel_id
    row_id = request.row_id
    tree_id = request.tree_id
    if tree_id is None and activity is not None:
        tree_id = activity.tree_id
        row_id = row_id or activity.row_id
        parcel_id = parcel_id or activity.parcel_id
    if tree_id is None and disease_case is not None:
        tree_id = disease_case.tree_id
        row_id = row_id or disease_case.row_id
        parcel_id = parcel_id or disease_case.parcel_id
    if tree_id is None and photo is not None:
        derived_parcel, derived_row, derived_tree = _ids_from_photo(photo, activity, disease_case)
        parcel_id = parcel_id or derived_parcel
        row_id = row_id or derived_row
        tree_id = derived_tree
    return parcel_id, row_id, tree_id


def _ids_from_photo(photo, activity, disease_case) -> tuple[UUID | None, UUID | None, UUID | None]:
    if photo.entity_type == AttachmentEntityType.TREE:
        return None, None, photo.entity_id
    if photo.entity_type == AttachmentEntityType.ROW:
        return None, photo.entity_id, None
    if photo.entity_type == AttachmentEntityType.PARCEL:
        return photo.entity_id, None, None
    if photo.entity_type == AttachmentEntityType.ACTIVITY and activity is not None:
        return activity.parcel_id, activity.row_id, activity.tree_id
    if photo.entity_type in {AttachmentEntityType.DISEASE_CASE, AttachmentEntityType.OBSERVATION} and disease_case is not None:
        return disease_case.parcel_id, disease_case.row_id, disease_case.tree_id
    return None, None, None


def _event_date(request: ContextRequest, photo, activity, disease_case) -> tuple[date, datetime | None]:
    if request.event_date is not None:
        return request.event_date, None
    if photo is not None and photo.taken_at is not None:
        taken = photo.taken_at
        return taken.date(), taken
    if disease_case is not None:
        return disease_case.detected_on, None
    if activity is not None:
        return activity.performed_on, None
    return date.today(), datetime.now(timezone.utc)
