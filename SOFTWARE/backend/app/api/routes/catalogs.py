from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.catalog import CatalogItemRead
from app.services.catalog import CatalogService

router = APIRouter(tags=["catalogs"])


@router.get("/activity-types", response_model=list[CatalogItemRead])
def list_activity_types(_current_user: CurrentUser, db: DBSession) -> list[CatalogItemRead]:
    return CatalogService(db).list_activity_types()


@router.get("/cost-categories", response_model=list[CatalogItemRead])
def list_cost_categories(_current_user: CurrentUser, db: DBSession) -> list[CatalogItemRead]:
    return CatalogService(db).list_cost_categories()
