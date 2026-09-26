from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import ActivityType
from app.models.cost import CostCategory


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_activity_types(self) -> list[ActivityType]:
        stmt = select(ActivityType).order_by(ActivityType.sort_order, ActivityType.name)
        return list(self.db.scalars(stmt).all())

    def get_activity_type(self, type_id: object) -> ActivityType | None:
        return self.db.get(ActivityType, type_id)

    def get_activity_type_by_slug(self, slug: str) -> ActivityType | None:
        stmt = select(ActivityType).where(ActivityType.slug == slug)
        return self.db.scalars(stmt).first()

    def list_cost_categories(self) -> list[CostCategory]:
        stmt = select(CostCategory).order_by(CostCategory.sort_order, CostCategory.name)
        return list(self.db.scalars(stmt).all())

    def get_cost_category(self, category_id: object) -> CostCategory | None:
        return self.db.get(CostCategory, category_id)

    def get_cost_category_by_slug(self, slug: str) -> CostCategory | None:
        return next((item for item in self.list_cost_categories() if item.slug == slug), None)
