from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AttachmentEntityType, DiseaseCaseStatus, DiseaseCategory, DiseaseSeverity
from app.schemas.common import IDSchema


class PhotoRead(IDSchema):
    farm_id: UUID
    entity_type: AttachmentEntityType
    entity_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    caption: str | None
    taken_at: datetime | None
    uploaded_by_id: UUID | None
    uploaded_at: datetime
    url: str


class ObservationCreate(BaseModel):
    observed_on: date
    symptoms: str | None = None
    notes: str | None = None


class ObservationRead(IDSchema):
    disease_case_id: UUID
    observed_on: date
    symptoms: str | None
    notes: str | None
    created_by_id: UUID | None
    photos: list[PhotoRead] = Field(default_factory=list)


class DiseaseCaseCreate(BaseModel):
    parcel_id: UUID
    row_id: UUID | None = None
    tree_id: UUID | None = None
    detected_on: date
    status: DiseaseCaseStatus = DiseaseCaseStatus.OPEN
    category: DiseaseCategory = DiseaseCategory.UNKNOWN
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    severity: DiseaseSeverity = DiseaseSeverity.MEDIUM
    notes: str | None = None
    symptoms: str | None = None
    tree_ids: list[UUID] = Field(default_factory=list)


class DiseaseCaseUpdate(BaseModel):
    status: DiseaseCaseStatus | None = None
    category: DiseaseCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    severity: DiseaseSeverity | None = None
    notes: str | None = None
    detected_on: date | None = None


class DiseaseCaseRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID
    row_id: UUID | None
    tree_id: UUID | None
    title: str
    description: str | None
    category: DiseaseCategory
    severity: DiseaseSeverity
    status: DiseaseCaseStatus
    detected_on: date
    resolved_on: date | None
    notes: str | None
    created_by_id: UUID | None
    parcel_name: str | None = None
    row_number: int | None = None
    tree_public_id: str | None = None
    observation_count: int = 0
    photo_count: int = 0


class DiseaseCaseDetailRead(DiseaseCaseRead):
    observations: list[ObservationRead] = Field(default_factory=list)
    photos: list[PhotoRead] = Field(default_factory=list)
