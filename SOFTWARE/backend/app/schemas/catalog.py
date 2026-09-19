from app.schemas.common import IDSchema


class CatalogItemRead(IDSchema):
    name: str
    slug: str
    description: str | None
    sort_order: int
