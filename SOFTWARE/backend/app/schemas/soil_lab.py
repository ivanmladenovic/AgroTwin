from datetime import date
from uuid import UUID

from app.schemas.common import IDSchema


class SoilLabAnalysisRead(IDSchema):
    activity_id: UUID
    parcel_id: UUID
    tree_id: UUID
    tree_public_id: str | None = None
    row_id: UUID | None = None
    row_number: int | None = None
    sampled_on: date
    original_filename: str
    content_type: str
    size_bytes: int | None
