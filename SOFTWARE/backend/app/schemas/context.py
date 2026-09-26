"""Versioned Context Engine DTOs. Schema version: 1.0."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.context.types import CONTEXT_VERSION, ContextRequestType, DataQualityStatus, TemporalRelation, WarningType


class ContextBuildRequest(BaseModel):
    request_type: ContextRequestType
    parcel_id: UUID | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None
    photo_id: UUID | None = None
    activity_id: UUID | None = None
    disease_case_id: UUID | None = None
    season_year: int | None = Field(default=None, ge=1990, le=2100)
    event_date: date | None = None
    query: str | None = Field(default=None, max_length=2000)
    include_debug: bool = False


class ProvenanceRead(BaseModel):
    source: str
    source_id: str | None = None
    source_type: str
    scope: str | None = None
    scope_id: UUID | None = None
    recorded_at: datetime | date | None = None
    retrieved_at: datetime
    relevance_score: float | None = None


class ContextWarningRead(BaseModel):
    type: WarningType
    source: str
    message: str


class ContextFarmRead(BaseModel):
    id: UUID
    name: str
    location_name: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class ContextParcelRead(BaseModel):
    id: UUID
    name: str
    code: str
    area_hectares: Decimal | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    altitude: Decimal | None = None
    row_count: int | None = None
    trees_per_row: int | None = None
    row_spacing_m: Decimal | None = None
    tree_spacing_m: Decimal | None = None
    default_variety: str | None = None
    varieties: list[dict[str, Any]] = Field(default_factory=list)
    default_planting_year: int | None = None
    tree_count: int | None = None
    notes: str | None = None
    has_boundary: bool = False


class ContextRowRead(BaseModel):
    id: UUID
    row_number: int
    name: str | None = None
    variety: str | None = None
    tree_count: int | None = None
    parcel_id: UUID


class ContextTreeRead(BaseModel):
    id: UUID
    public_id: str
    row_id: UUID
    parcel_id: UUID
    position_in_row: int
    variety: str | None = None
    planting_year: int | None = None
    status: str
    health_status: str
    notes: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class ContextSubjectRead(BaseModel):
    type: str
    farm: ContextFarmRead
    parcel: ContextParcelRead | None = None
    row: ContextRowRead | None = None
    tree: ContextTreeRead | None = None


class ContextCropRead(BaseModel):
    variety: str | None = None
    varieties: list[dict[str, Any]] = Field(default_factory=list)
    planting_year: int | None = None
    age_years: int | None = None


class ContextRequestEcho(BaseModel):
    type: ContextRequestType
    query: str | None = None
    season_year: int | None = None
    event_date: date
    parcel_id: UUID | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None
    photo_id: UUID | None = None
    activity_id: UUID | None = None
    disease_case_id: UUID | None = None


class ContextActivityItem(BaseModel):
    id: UUID
    type: str
    title: str
    date: date
    scope: str
    scope_id: UUID | None = None
    status: str
    quantity: Decimal | None = None
    unit: str | None = None
    notes: str | None = None
    temporal_relation: TemporalRelation
    relevance_score: float
    provenance: ProvenanceRead


class ContextCostItem(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    incurred_on: date
    description: str
    category: str
    activity_id: UUID
    scope: str
    scope_id: UUID | None = None
    relevance_score: float
    provenance: ProvenanceRead


class ContextCostSummary(BaseModel):
    status: DataQualityStatus
    currency: str = "EUR"
    total: Decimal | None = None
    by_category: list[dict[str, Any]] = Field(default_factory=list)
    by_activity_type: list[dict[str, Any]] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    scope: str | None = None
    items: list[ContextCostItem] = Field(default_factory=list)


class ContextWeatherDay(BaseModel):
    date: date
    min_temperature: float | None = None
    max_temperature: float | None = None
    precipitation: float | None = None


class ContextWeatherRead(BaseModel):
    status: DataQualityStatus
    source: str = "Yr / MET Norway"
    source_type: str = "external_weather_data"
    scope: str = "PARCEL"
    is_stale: bool = False
    fetched_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    minimum_temperature: float | None = None
    maximum_temperature: float | None = None
    average_temperature: float | None = None
    precipitation: float | None = None
    rainy_days: int | None = None
    hot_days: int | None = None
    frost_days: int | None = None
    days: list[ContextWeatherDay] = Field(default_factory=list)
    message: str | None = None


class ContextSoilProperty(BaseModel):
    key: str
    label: str
    unit: str
    value: float | None = None
    depth: str | None = None
    depth_label: str | None = None
    available: bool = False


class ContextSoilRead(BaseModel):
    status: DataQualityStatus
    source: str = "SoilGrids"
    source_type: Literal["modeled_estimate"] = "modeled_estimate"
    source_label: str = "Modelovana procena – SoilGrids"
    is_stale: bool = False
    is_modeled: bool = True
    fetched_at: datetime | None = None
    depth: str | None = None
    properties: dict[str, ContextSoilProperty] = Field(default_factory=dict)
    missing_properties: list[str] = Field(default_factory=list)
    message: str | None = None


class ContextHarvestItem(BaseModel):
    id: UUID
    harvested_on: date
    gross_quantity: Decimal
    loss_quantity: Decimal
    net_quantity: Decimal
    unit: str
    quality_category: str | None = None
    moisture_percent: Decimal | None = None
    damaged_percent: Decimal | None = None
    empty_nuts_percent: Decimal | None = None
    scope: str
    scope_id: UUID | None = None
    temporal_relation: TemporalRelation
    relevance_score: float
    provenance: ProvenanceRead


class ContextHarvestRead(BaseModel):
    status: DataQualityStatus
    event_count: int = 0
    gross_quantity: Decimal | None = None
    loss_quantity: Decimal | None = None
    net_quantity: Decimal | None = None
    first_harvest_on: date | None = None
    last_harvest_on: date | None = None
    items: list[ContextHarvestItem] = Field(default_factory=list)


class ContextPhotoItem(BaseModel):
    id: UUID
    date: datetime | None = None
    scope: str
    parcel_id: UUID | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None
    entity_type: str
    entity_id: UUID
    category: str | None = None
    notes: str | None = None
    original_filename: str
    content_type: str
    storage_key: str
    url: str
    is_current: bool = False
    temporal_relation: TemporalRelation
    relevance_score: float
    provenance: ProvenanceRead


class ContextAIItem(BaseModel):
    id: UUID
    date: datetime
    finding: str
    confidence: float
    source_type: Literal["previous_ai_analysis"] = "previous_ai_analysis"
    observed_symptoms: list[str] = Field(default_factory=list)
    observed_facts: str | None = None
    uncertainty_notes: str | None = None
    photo_id: UUID | None = None
    disease_case_id: UUID
    scope: str
    scope_id: UUID | None = None
    provider: str | None = None
    model: str | None = None
    temporal_relation: TemporalRelation
    relevance_score: float
    provenance: ProvenanceRead


class ContextProblemItem(BaseModel):
    id: UUID
    title: str
    category: str
    severity: str
    status: str
    detected_on: date
    description: str | None = None
    scope: str
    scope_id: UUID | None = None
    temporal_relation: TemporalRelation
    relevance_score: float
    provenance: ProvenanceRead


class ContextKnowledgeQuery(BaseModel):
    problem: str | None = None
    topics: list[str] = Field(default_factory=list)


class DebugRecordRead(BaseModel):
    kind: str
    id: str
    scope: str | None = None
    date: date | datetime | None = None
    relevance_score: float
    selected: bool
    reasons: list[str] = Field(default_factory=list)
    temporal_relation: TemporalRelation | None = None


class ContextDebugRead(BaseModel):
    providers_used: list[str] = Field(default_factory=list)
    provider_failures: list[dict[str, str]] = Field(default_factory=list)
    collected: dict[str, int] = Field(default_factory=dict)
    filtered: dict[str, int] = Field(default_factory=dict)
    selected: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0
    records: list[DebugRecordRead] = Field(default_factory=list)


class DataQualityMap(BaseModel):
    parcel: DataQualityStatus = DataQualityStatus.AVAILABLE
    soil: DataQualityStatus = DataQualityStatus.MISSING
    weather: DataQualityStatus = DataQualityStatus.MISSING
    activities: DataQualityStatus = DataQualityStatus.MISSING
    costs: DataQualityStatus | None = None
    harvest: DataQualityStatus | None = None
    photos: DataQualityStatus = DataQualityStatus.MISSING
    previous_ai_analyses: DataQualityStatus = DataQualityStatus.MISSING
    problems: DataQualityStatus | None = None


class AgroTwinContext(BaseModel):
    context_id: UUID
    context_version: str = CONTEXT_VERSION
    created_at: datetime
    request: ContextRequestEcho
    subject: ContextSubjectRead
    crop: ContextCropRead
    soil: ContextSoilRead | None = None
    weather: ContextWeatherRead | None = None
    activities: list[ContextActivityItem] = Field(default_factory=list)
    activity_summary: dict[str, Any] | None = None
    costs: ContextCostSummary | None = None
    harvest: ContextHarvestRead | None = None
    photos: list[ContextPhotoItem] = Field(default_factory=list)
    previous_ai_analyses: list[ContextAIItem] = Field(default_factory=list)
    problems: list[ContextProblemItem] = Field(default_factory=list)
    knowledge_query: ContextKnowledgeQuery | None = None
    data_quality: DataQualityMap
    warnings: list[ContextWarningRead] = Field(default_factory=list)
    provenance: list[ProvenanceRead] = Field(default_factory=list)
    debug: ContextDebugRead | None = None
