from datetime import date
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.deps import CurrentUser, DBSession
from app.schemas.soil_lab import SoilLabAnalysisRead
from app.services.soil_lab import SoilLabAnalysisService

router = APIRouter(tags=["soil-lab"])


@router.get("/parcels/{parcel_id}/soil-analyses", response_model=list[SoilLabAnalysisRead])
def list_parcel_soil_analyses(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> list[SoilLabAnalysisRead]:
    return SoilLabAnalysisService(db).list_for_parcel(parcel_id, current_user.id)


@router.post("/parcels/{parcel_id}/soil-analyses", response_model=SoilLabAnalysisRead, status_code=201)
async def create_parcel_soil_analysis(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
    tree_id: UUID = Form(...),
    sampled_on: date = Form(...),
) -> SoilLabAnalysisRead:
    content = await file.read()
    service = SoilLabAnalysisService(db)
    analysis = service.create_for_parcel(
        parcel_id,
        current_user.id,
        tree_id=tree_id,
        sampled_on=sampled_on,
        filename=file.filename or "analiza.pdf",
        content_type=file.content_type or "application/pdf",
        content=content,
        created_by_id=current_user.id,
    )
    return service.to_read(analysis)


@router.get("/activities/{activity_id}/soil-analyses", response_model=list[SoilLabAnalysisRead])
def list_soil_analyses(activity_id: UUID, current_user: CurrentUser, db: DBSession) -> list[SoilLabAnalysisRead]:
    return SoilLabAnalysisService(db).list_for_activity(activity_id, current_user.id)


@router.post("/activities/{activity_id}/soil-analyses", response_model=SoilLabAnalysisRead, status_code=201)
async def create_soil_analysis(
    activity_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
    tree_id: UUID = Form(...),
    sampled_on: date = Form(...),
) -> SoilLabAnalysisRead:
    content = await file.read()
    service = SoilLabAnalysisService(db)
    analysis = service.create(
        activity_id,
        current_user.id,
        tree_id=tree_id,
        sampled_on=sampled_on,
        filename=file.filename or "analiza.pdf",
        content_type=file.content_type or "application/pdf",
        content=content,
        created_by_id=current_user.id,
    )
    return service.to_read(analysis)


@router.get("/soil-analyses/{analysis_id}/file")
def get_soil_analysis_file(analysis_id: UUID, current_user: CurrentUser, db: DBSession) -> Response:
    service = SoilLabAnalysisService(db)
    analysis = service.get_analysis(analysis_id, current_user.id)
    local = service.file_local_path(analysis)
    if local is not None and local.exists():
        return FileResponse(local, media_type=analysis.content_type, filename=analysis.original_filename)
    content, content_type = service.file_bytes(analysis)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{analysis.original_filename}"'},
    )


@router.delete("/soil-analyses/{analysis_id}", status_code=204)
def delete_soil_analysis(analysis_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    SoilLabAnalysisService(db).delete(analysis_id, current_user.id)
