from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DBSession
from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: DBSession) -> HealthResponse:
    settings = get_settings()
    db.execute(text("SELECT 1"))
    return HealthResponse(status="ok", service=settings.app_name, database="connected")
