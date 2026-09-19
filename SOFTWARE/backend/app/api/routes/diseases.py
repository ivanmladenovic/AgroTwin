from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.deps import CurrentUser, DBSession
from app.models.enums import AttachmentEntityType, DiseaseCaseStatus, DiseaseCategory
from app.schemas.disease import (
    DiseaseCaseCreate,
    DiseaseCaseDetailRead,
    DiseaseCaseRead,
    DiseaseCaseUpdate,
    ObservationCreate,
    ObservationRead,
    PhotoRead,
)
from app.services.disease import DiseaseService

router = APIRouter(tags=["health"])


@router.get("/disease-cases", response_model=list[DiseaseCaseRead])
def list_disease_cases(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
    row_id: UUID | None = None,
    tree_id: UUID | None = None,
    status: DiseaseCaseStatus | None = None,
    category: DiseaseCategory | None = None,
) -> list[DiseaseCaseRead]:
    return DiseaseService(db).list_cases(
        current_user.id,
        parcel_id=parcel_id,
        row_id=row_id,
        tree_id=tree_id,
        status=status,
        category=category,
    )


@router.post("/disease-cases", response_model=DiseaseCaseDetailRead, status_code=201)
def create_disease_case(
    payload: DiseaseCaseCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> DiseaseCaseDetailRead:
    service = DiseaseService(db)
    case = service.create_case(current_user.id, payload, current_user.id)
    return service.get_case_detail(case.id, current_user.id)


@router.get("/disease-cases/{case_id}", response_model=DiseaseCaseDetailRead)
def get_disease_case(case_id: UUID, current_user: CurrentUser, db: DBSession) -> DiseaseCaseDetailRead:
    return DiseaseService(db).get_case_detail(case_id, current_user.id)


@router.patch("/disease-cases/{case_id}", response_model=DiseaseCaseDetailRead)
def update_disease_case(
    case_id: UUID,
    payload: DiseaseCaseUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> DiseaseCaseDetailRead:
    service = DiseaseService(db)
    case = service.update_case(case_id, current_user.id, payload)
    return service.get_case_detail(case.id, current_user.id)


@router.post("/disease-cases/{case_id}/observations", response_model=ObservationRead, status_code=201)
def add_observation(
    case_id: UUID,
    payload: ObservationCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> ObservationRead:
    service = DiseaseService(db)
    observation = service.add_observation(case_id, current_user.id, payload, current_user.id)
    return service.to_observation_read(observation)


@router.post("/photos", response_model=PhotoRead, status_code=201)
async def upload_photo(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
    entity_type: AttachmentEntityType = Form(...),
    entity_id: UUID = Form(...),
    caption: str | None = Form(default=None),
) -> PhotoRead:
    content = await file.read()
    service = DiseaseService(db)
    photo = service.add_photo(
        current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        filename=file.filename or "photo",
        content_type=file.content_type or "application/octet-stream",
        content=content,
        caption=caption,
        uploaded_by_id=current_user.id,
    )
    return service.to_photo_read(photo)


@router.get("/photos/{photo_id}", response_model=PhotoRead)
def get_photo(photo_id: UUID, current_user: CurrentUser, db: DBSession) -> PhotoRead:
    service = DiseaseService(db)
    return service.to_photo_read(service.get_photo(photo_id, current_user.id))


@router.get("/photos/{photo_id}/file")
def get_photo_file(photo_id: UUID, current_user: CurrentUser, db: DBSession) -> Response:
    service = DiseaseService(db)
    photo = service.get_photo(photo_id, current_user.id)
    local = service.photo_local_path(photo)
    if local is not None and local.exists():
        return FileResponse(local, media_type=photo.content_type, filename=photo.original_filename)
    content, content_type = service.photo_bytes(photo)
    return Response(content=content, media_type=content_type)
