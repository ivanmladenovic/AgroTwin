from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import SoilLabExtractionStatus, SoilLabVerificationStatus
from app.schemas.common import IDSchema


class SoilLabResultRead(IDSchema):
    analysis_id: UUID
    parameter_code: str
    original_parameter_name: str
    value: str
    unit: str | None = None
    method: str | None = None
    depth_from_cm: Decimal | None = None
    depth_to_cm: Decimal | None = None
    extraction_confidence: Decimal | None = None
    source_page: int | None = None
    raw_text: str | None = None
    verification_status: SoilLabVerificationStatus
    notes: str | None = None
    high_confidence: bool = False


class SoilLabAnalysisRead(IDSchema):
    activity_id: UUID
    parcel_id: UUID
    tree_id: UUID
    tree_public_id: str | None = None
    row_id: UUID | None = None
    row_number: int | None = None
    sampled_on: date
    analysis_date: date | None = None
    laboratory_name: str | None = None
    sample_depth_from_cm: Decimal | None = None
    sample_depth_to_cm: Decimal | None = None
    original_filename: str
    content_type: str
    size_bytes: int | None
    extraction_status: SoilLabExtractionStatus = SoilLabExtractionStatus.PENDING
    verification_status: SoilLabVerificationStatus = SoilLabVerificationStatus.NEEDS_REVIEW
    extraction_error: str | None = None
    result_count: int = 0
    results: list[SoilLabResultRead] = Field(default_factory=list)
    source_kind: str = "laboratory"


class SoilLabResultUpdate(BaseModel):
    parameter_code: str | None = None
    original_parameter_name: str | None = None
    value: str | None = None
    unit: str | None = None
    method: str | None = None
    depth_from_cm: Decimal | None = None
    depth_to_cm: Decimal | None = None
    notes: str | None = None
    verification_status: SoilLabVerificationStatus | None = None


class SoilLabResultCreate(BaseModel):
    parameter_code: str
    original_parameter_name: str
    value: str
    unit: str | None = None
    method: str | None = None
    depth_from_cm: Decimal | None = None
    depth_to_cm: Decimal | None = None
    notes: str | None = None


class SoilLabVerifyRequest(BaseModel):
    analysis_date: date | None = None
    laboratory_name: str | None = None
    sample_depth_from_cm: Decimal | None = None
    sample_depth_to_cm: Decimal | None = None
