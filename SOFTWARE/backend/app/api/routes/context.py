from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.context import AgroTwinContext, ContextBuildRequest
from app.services.context import ContextService

router = APIRouter(prefix="/context", tags=["context"])


@router.post("/build", response_model=AgroTwinContext)
def build_context(payload: ContextBuildRequest, current_user: CurrentUser, db: DBSession) -> AgroTwinContext:
    return ContextService(db).build(current_user.id, payload)


@router.post("/preview", response_model=AgroTwinContext)
def preview_context(payload: ContextBuildRequest, current_user: CurrentUser, db: DBSession) -> AgroTwinContext:
    debug_payload = payload.model_copy(update={"include_debug": True})
    return ContextService(db).build(current_user.id, debug_payload)
