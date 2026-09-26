from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.soil.properties import PROVIDER_NAME, SOURCE_EXPLANATION, SOURCE_LABEL, SOURCE_TYPE, SPATIAL_RESOLUTION

SoilStatus = Literal[
    "ok",
    "partial",
    "stale",
    "location_required",
    "unavailable",
    "rate_limited",
    "timeout",
    "malformed",
]


class SoilDepthValueRead(BaseModel):
    depth: str
    depth_label: str
    value: float
    unit: str
    uncertainty: float | None = None
    lower: float | None = None
    upper: float | None = None


class SoilPropertyRead(BaseModel):
    key: str
    label: str
    unit: str
    value: float | None = None
    depth: str | None = None
    depth_label: str | None = None
    source: str = PROVIDER_NAME
    source_type: Literal["modeled_estimate"] = SOURCE_TYPE
    source_label: str = SOURCE_LABEL
    measured_at: datetime | None = None
    generated_at: datetime | None = None
    is_modeled: bool = True
    available: bool = True
    depths: list[SoilDepthValueRead] = Field(default_factory=list)


class ParcelSoilProfileRead(BaseModel):
    available: bool
    status: SoilStatus
    is_stale: bool = False
    message: str | None = None
    parcel_id: UUID
    parcel_name: str
    latitude: float | None = None
    longitude: float | None = None
    provider: str = PROVIDER_NAME
    source: str = PROVIDER_NAME
    source_type: Literal["modeled_estimate"] = SOURCE_TYPE
    source_label: str = SOURCE_LABEL
    source_explanation: str = SOURCE_EXPLANATION
    dataset_version: str | None = None
    spatial_resolution: str = SPATIAL_RESOLUTION
    fetched_at: datetime | None = None
    generated_at: datetime | None = None
    is_modeled: bool = True
    can_refresh: bool = False
    refresh_available_at: datetime | None = None
    depths: list[str] = Field(default_factory=list)
    properties: list[SoilPropertyRead] = Field(default_factory=list)
    missing_properties: list[str] = Field(default_factory=list)
