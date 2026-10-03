from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness for Render — keep this free of DB/AI so long chat work cannot trip restarts."""
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name, database="skipped")
