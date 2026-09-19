from app.api.deps import CurrentUser, DBSession
from app.schemas.dashboard import DashboardRead
from app.services.dashboard import DashboardService
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(current_user: CurrentUser, db: DBSession) -> DashboardRead:
    return DashboardService(db).get_overview(current_user)
