from sqlalchemy.orm import Session

from app.core.catalogs import ACTIVITY_TYPES, COST_CATEGORIES
from app.models.activity import ActivityType
from app.models.cost import CostCategory
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import CatalogItemRead


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalogs = CatalogRepository(db)

    def list_activity_types(self) -> list[CatalogItemRead]:
        return [CatalogItemRead.model_validate(item) for item in self.catalogs.list_activity_types()]

    def list_cost_categories(self) -> list[CatalogItemRead]:
        return [CatalogItemRead.model_validate(item) for item in self.catalogs.list_cost_categories()]

    def upsert_defaults(self) -> None:
        existing_types = {item.slug: item for item in self.catalogs.list_activity_types()}
        for index, (slug, name, description) in enumerate(ACTIVITY_TYPES):
            current = existing_types.get(slug)
            if current is None:
                self.db.add(
                    ActivityType(slug=slug, name=name, description=description, sort_order=index)
                )
            else:
                current.name = name
                current.description = description
                current.sort_order = index

        existing_categories = {item.slug: item for item in self.catalogs.list_cost_categories()}
        for index, (slug, name, description) in enumerate(COST_CATEGORIES):
            current = existing_categories.get(slug)
            if current is None:
                self.db.add(
                    CostCategory(slug=slug, name=name, description=description, sort_order=index)
                )
            else:
                current.name = name
                current.description = description
                current.sort_order = index
        self.db.flush()
