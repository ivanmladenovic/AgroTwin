from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseOrgStatus,
    EnterprisePurchaseCurrency,
    EnterpriseQuantityBasis,
    EnterpriseRelationshipStatus,
    EnterpriseScenarioType,
    EnterpriseSeasonStatus,
    EnterpriseYieldPlanStatus,
)
from app.schemas.common import IDSchema, ORMModel


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class EnterpriseOrganizationRead(IDSchema):
    name: str
    slug: str
    logo_url: str | None = None
    description: str | None = None
    country: str | None = None
    default_currency: str
    timezone: str
    default_crop: str | None = None
    status: EnterpriseOrgStatus
    default_scenario: EnterpriseScenarioType
    completeness_requirements: dict = Field(default_factory=dict)


class EnterpriseOrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo_url: str | None = None
    description: str | None = None
    country: str | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=8)
    timezone: str | None = None
    default_crop: str | None = None
    default_scenario: EnterpriseScenarioType | None = None
    completeness_requirements: dict | None = None


class EnterpriseMembershipRead(IDSchema):
    organization_id: UUID
    user_id: UUID
    role: EnterpriseMembershipRole
    status: EnterpriseMembershipStatus
    organization: EnterpriseOrganizationRead | None = None
    user_email: EmailStr | None = None
    user_full_name: str | None = None


class EnterpriseMembershipCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: EnterpriseMembershipRole = EnterpriseMembershipRole.ENTERPRISE_VIEWER
    temporary_password: str | None = Field(default=None, min_length=8, max_length=128)


class EnterpriseMembershipUpdate(BaseModel):
    role: EnterpriseMembershipRole | None = None
    status: EnterpriseMembershipStatus | None = None


class EnterpriseSupplierLinkRead(IDSchema):
    organization_id: UUID
    farm_id: UUID
    status: EnterpriseRelationshipStatus
    relationship_start: date | None = None
    relationship_end: date | None = None
    internal_code: str | None = None
    internal_group: str | None = None
    internal_notes: str | None = None
    assigned_at: datetime
    farm_name: str | None = None
    farm_location: str | None = None
    # Display name for the producer account (person/company), not the orchard name.
    producer_display_name: str | None = None
    owner_full_name: str | None = None
    public_producer_name: str | None = None
    assigned_parcel_count: int = 0
    assigned_area_ha: Decimal | None = None
    expected_yield_kg: Decimal | None = None
    actual_yield_kg: Decimal | None = None
    completeness_avg: float | None = None


class EnterpriseSupplierLinkCreate(BaseModel):
    farm_id: UUID
    status: EnterpriseRelationshipStatus = EnterpriseRelationshipStatus.ACTIVE
    relationship_start: date | None = None
    relationship_end: date | None = None
    internal_code: str | None = Field(default=None, max_length=64)
    internal_group: str | None = Field(default=None, max_length=128)
    internal_notes: str | None = None


class EnterpriseSupplierLinkUpdate(BaseModel):
    status: EnterpriseRelationshipStatus | None = None
    relationship_start: date | None = None
    relationship_end: date | None = None
    internal_code: str | None = Field(default=None, max_length=64)
    internal_group: str | None = Field(default=None, max_length=128)
    internal_notes: str | None = None


class EnterpriseParcelAssignmentRead(IDSchema):
    organization_id: UUID
    farm_id: UUID
    parcel_id: UUID
    status: EnterpriseAssignmentStatus
    valid_from: date | None = None
    valid_until: date | None = None
    assigned_at: datetime
    parcel_name: str | None = None
    farm_name: str | None = None
    area_hectares: Decimal | None = None


class EnterpriseParcelAssignmentCreate(BaseModel):
    parcel_id: UUID
    status: EnterpriseAssignmentStatus = EnterpriseAssignmentStatus.ACTIVE
    valid_from: date | None = None
    valid_until: date | None = None


class EnterpriseParcelAssignmentUpdate(BaseModel):
    status: EnterpriseAssignmentStatus | None = None
    valid_from: date | None = None
    valid_until: date | None = None


class EnterprisePlanningSeasonRead(IDSchema):
    organization_id: UUID
    year: int
    name: str
    status: EnterpriseSeasonStatus
    supply_target_kg: Decimal | None = None


class EnterprisePlanningSeasonCreate(BaseModel):
    year: int = Field(ge=1990, le=2100)
    name: str = Field(min_length=1, max_length=255)
    status: EnterpriseSeasonStatus = EnterpriseSeasonStatus.DRAFT
    supply_target_kg: Decimal | None = None


class EnterprisePlanningSeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: EnterpriseSeasonStatus | None = None
    supply_target_kg: Decimal | None = None


class EnterpriseYieldPlanItemRead(IDSchema):
    yield_plan_id: UUID
    farm_id: UUID
    parcel_id: UUID
    crop: str
    forecast_area_ha: Decimal | None = None
    forecast_tree_count: int | None = None
    forecast_yield_kg: Decimal
    forecast_yield_tonnes: Decimal | None = None
    forecast_yield_kg_per_ha: Decimal | None = None
    scenario_assumptions: dict = Field(default_factory=dict)
    source_snapshot: dict = Field(default_factory=dict)
    calculation_version: str
    data_quality: dict = Field(default_factory=dict)
    parcel_name: str | None = None
    farm_name: str | None = None


class EnterpriseYieldPlanRead(IDSchema):
    organization_id: UUID
    planning_season_id: UUID
    name: str
    description: str | None = None
    scenario_type: EnterpriseScenarioType
    status: EnterpriseYieldPlanStatus
    assumptions: dict = Field(default_factory=dict)
    calculation_version: str
    created_by_id: UUID | None = None
    items: list[EnterpriseYieldPlanItemRead] = Field(default_factory=list)
    total_forecast_kg: Decimal | None = None


class EnterpriseYieldPlanCreate(BaseModel):
    planning_season_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scenario_type: EnterpriseScenarioType = EnterpriseScenarioType.REALISTIC
    assumptions: dict = Field(default_factory=dict)
    parcel_ids: list[UUID] | None = None


class EnterpriseParcelSummary(ORMModel):
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    area_hectares: Decimal | None = None
    tree_count: int = 0
    default_variety: str | None = None
    varieties: list[dict] = Field(default_factory=list)
    variety_names: list[str] = Field(default_factory=list)
    default_planting_year: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    has_boundary: bool = False
    completeness_score: float | None = None
    missing_fields: list[str] = Field(default_factory=list)
    expected_yield_kg: Decimal | None = None
    latest_harvest_kg: Decimal | None = None


class EnterpriseActivityBrief(BaseModel):
    id: UUID
    title: str
    performed_on: date
    status: str
    semantic_type: str | None = None
    activity_type_name: str | None = None


class EnterpriseHarvestYearBrief(BaseModel):
    year: int
    net_kg: Decimal | None = None
    event_count: int = 0


class EnterpriseParcelDetail(EnterpriseParcelSummary):
    boundary: dict | None = None
    maps_url: str | None = None
    row_count: int | None = None
    trees_per_row: int | None = None
    planting_year_distribution: dict[str, int] = Field(default_factory=dict)
    harvest_years: list[int] = Field(default_factory=list)
    harvest_by_year: list[EnterpriseHarvestYearBrief] = Field(default_factory=list)
    latest_harvest_kg: Decimal | None = None
    expected_yield_kg: Decimal | None = None
    recent_activities: list[EnterpriseActivityBrief] = Field(default_factory=list)
    activity_counts: dict[str, int] = Field(default_factory=dict)
    protection_count: int = 0
    fertilization_count: int = 0
    irrigation_count: int = 0
    observation_count: int = 0


class EnterpriseDashboardKPIs(BaseModel):
    active_suppliers: int
    assigned_farms: int
    assigned_parcels: int
    total_area_ha: Decimal | None = None
    total_trees: int | None = None
    expected_yield_kg: Decimal | None = None
    actual_yield_kg: Decimal | None = None
    harvest_coverage_percent: float | None = None
    parcels_missing_key_data: int
    parcels_with_issues: int
    season_year: int | None = None
    notes: list[str] = Field(default_factory=list)


class EnterpriseMapParcel(BaseModel):
    parcel_id: UUID
    parcel_name: str
    producer_display_name: str | None = None
    latitude: float
    longitude: float
    area_hectares: Decimal | None = None
    tree_count: int = 0
    completeness_score: float | None = None
    issue_trees: int = 0
    monitoring_trees: int = 0
    healthy_trees: int = 0
    open_cases: int = 0


class EnterpriseYearProductionRow(BaseModel):
    year: int
    expected_yield_kg: Decimal | None = None
    actual_yield_kg: Decimal | None = None
    parcels_with_harvest: int = 0
    assigned_parcels: int = 0


class EnterpriseVarietyProductionRow(BaseModel):
    variety: str
    tree_count: int = 0
    expected_yield_kg: Decimal | None = None
    actual_yield_kg: Decimal | None = None
    share_of_trees_percent: float | None = None


class EnterpriseProductionAnalytics(BaseModel):
    by_year: list[EnterpriseYearProductionRow] = Field(default_factory=list)
    by_variety: list[EnterpriseVarietyProductionRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EnterpriseAggregateParcelSlice(BaseModel):
    parcel_id: UUID
    parcel_name: str
    producer_display_name: str | None = None
    area_hectares: Decimal | None = None
    tree_count: int = 0
    variety_names: list[str] = Field(default_factory=list)
    expected_yield_kg: Decimal | None = None
    actual_yield_kg: Decimal | None = None
    activity_count: int | None = None
    completeness_score: float | None = None


class EnterpriseAggregatePurchaseSlice(BaseModel):
    purchase_id: UUID
    farm_id: UUID
    producer_display_name: str | None = None
    farm_name: str | None = None
    purchased_on: date
    quantity_kg: Decimal
    quantity_basis: EnterpriseQuantityBasis
    currency: EnterprisePurchaseCurrency
    unit_price_per_kg: Decimal
    total_amount: Decimal
    notes: str | None = None


class EnterpriseAggregatePurchaseSupplierRow(BaseModel):
    farm_id: UUID
    producer_display_name: str | None = None
    farm_name: str | None = None
    purchase_count: int = 0
    quantity_kg: Decimal | None = None
    amount_by_currency: dict[str, Decimal] = Field(default_factory=dict)


class EnterpriseAggregateReport(BaseModel):
    organization_name: str
    year: int
    generated_on: date
    parcel_count: int
    total_area_ha: Decimal | None = None
    total_trees: int | None = None
    expected_yield_kg: Decimal | None = None
    actual_yield_kg: Decimal | None = None
    harvest_coverage_percent: float | None = None
    parcels: list[EnterpriseAggregateParcelSlice] = Field(default_factory=list)
    purchase_count: int = 0
    purchased_quantity_kg: Decimal | None = None
    purchase_totals_by_currency: dict[str, Decimal] = Field(default_factory=dict)
    purchases: list[EnterpriseAggregatePurchaseSlice] = Field(default_factory=list)
    purchases_by_supplier: list[EnterpriseAggregatePurchaseSupplierRow] = Field(
        default_factory=list
    )
    notes: list[str] = Field(default_factory=list)


class EnterpriseAggregateReportRequest(BaseModel):
    parcel_ids: list[UUID] = Field(min_length=1)
    year: int | None = Field(default=None, ge=1990, le=2100)


class EnterpriseMeResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    must_change_password: bool
    memberships: list[EnterpriseMembershipRead]


class EnterpriseFarmCandidate(BaseModel):
    farm_id: UUID
    name: str
    location_name: str | None = None
    already_linked: bool = False


class EnterpriseAssignableParcel(BaseModel):
    parcel_id: UUID
    farm_id: UUID
    name: str
    area_hectares: Decimal | None = None
    already_assigned: bool = False


class EnterpriseYieldComparisonRow(BaseModel):
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str | None = None
    farm_name: str | None = None
    forecast_yield_kg: Decimal
    actual_net_yield_kg: Decimal | None = None
    difference_kg: Decimal | None = None
    difference_percent: float | None = None
    status: str  # matched | missing_harvest | forecast_zero | compared
    harvest_events: int = 0


class EnterpriseYieldComparison(BaseModel):
    plan_id: UUID
    plan_name: str
    scenario_type: EnterpriseScenarioType
    season_year: int
    total_forecast_kg: Decimal
    total_actual_kg: Decimal | None = None
    parcels_with_harvest: int
    parcels_missing_harvest: int
    rows: list[EnterpriseYieldComparisonRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# --- Orchard monitoring / attention center ---


class EnterpriseMetricAvailability(BaseModel):
    """KPI or section metric. Use available=False instead of inventing zero."""

    available: bool
    value: int | None = None
    note: str | None = None


class EnterpriseAttentionItem(BaseModel):
    id: str
    category: str
    category_label: str
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    event_date: date | None = None
    title: str
    description: str | None = None
    source: str
    review_status: str | None = None
    severity: str | None = None
    reason: str
    source_type: str
    source_id: UUID
    priority_rank: int = 40


class EnterpriseMonitoringObservationItem(BaseModel):
    id: UUID
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    performed_on: date
    title: str
    description: str | None = None
    semantic_type: str | None = None
    observation_category: str | None = None
    observation_severity: str | None = None
    observation_status: str | None = None
    activity_status: str
    activity_type_name: str | None = None
    source: str
    photo_url: str | None = None
    follow_up_of_id: UUID | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None
    category: str


class EnterpriseMonitoringActivityItem(BaseModel):
    id: UUID
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    performed_on: date
    title: str
    description: str | None = None
    semantic_type: str | None = None
    activity_type_name: str | None = None
    status: str
    source: str


class EnterpriseMonitoringPlanItem(BaseModel):
    id: UUID
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    title: str
    description: str | None = None
    planned_date_from: date | None = None
    planned_date_to: date | None = None
    status: str
    priority_level: str | None = None
    item_kind: str | None = None
    bucket: str
    source: str


class EnterpriseWeatherSignal(BaseModel):
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    signal_kind: str
    title: str
    detail: str
    period_start: date | None = None
    period_end: date | None = None
    source: str
    observed_value: str | None = None
    threshold: str | None = None
    reason: str
    is_forecast: bool = True
    has_matching_observation: bool = False


class EnterpriseDataQualityItem(BaseModel):
    parcel_id: UUID
    farm_id: UUID
    parcel_name: str
    farm_name: str
    producer_display_name: str | None = None
    kind: str
    detail: str
    missing_fields: list[str] = Field(default_factory=list)
    completeness_score: float | None = None
    reference_date: date | None = None


class EnterpriseMonitoringKpis(BaseModel):
    open_problems: EnterpriseMetricAvailability
    new_observations: EnterpriseMetricAvailability
    pending_plan_tasks: EnterpriseMetricAvailability
    parcels_for_review: EnterpriseMetricAvailability
    incomplete_data: EnterpriseMetricAvailability
    stale_data: EnterpriseMetricAvailability


class EnterpriseMonitoringFiltersMeta(BaseModel):
    suppliers: list[dict] = Field(default_factory=list)
    parcels: list[dict] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    review_statuses: list[str] = Field(default_factory=list)
    severities: list[str] = Field(default_factory=list)


class EnterpriseMonitoringCenter(BaseModel):
    season_year: int
    period_from: date
    period_to: date
    kpis: EnterpriseMonitoringKpis
    attention_items: list[EnterpriseAttentionItem] = Field(default_factory=list)
    observations: list[EnterpriseMonitoringObservationItem] = Field(default_factory=list)
    activities: list[EnterpriseMonitoringActivityItem] = Field(default_factory=list)
    plan_items: list[EnterpriseMonitoringPlanItem] = Field(default_factory=list)
    weather_signals: list[EnterpriseWeatherSignal] = Field(default_factory=list)
    data_quality: list[EnterpriseDataQualityItem] = Field(default_factory=list)
    weather: EnterpriseMetricAvailability
    filters: EnterpriseMonitoringFiltersMeta
    notes: list[str] = Field(default_factory=list)
    category_labels: dict[str, str] = Field(default_factory=dict)


# --- Otkup (purchase) ---


class EnterpriseSupplierPriceUpsert(BaseModel):
    farm_id: UUID
    season_year: int = Field(ge=1990, le=2100)
    currency: EnterprisePurchaseCurrency = EnterprisePurchaseCurrency.RSD
    price_bruto_per_kg: Decimal | None = Field(default=None, ge=0)
    price_neto_per_kg: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class EnterpriseSupplierPriceRead(IDSchema):
    organization_id: UUID
    farm_id: UUID
    season_year: int
    currency: EnterprisePurchaseCurrency
    price_bruto_per_kg: Decimal | None = None
    price_neto_per_kg: Decimal | None = None
    notes: str | None = None
    producer_display_name: str | None = None
    farm_name: str | None = None


class EnterprisePurchaseCreate(BaseModel):
    farm_id: UUID
    purchased_on: date
    quantity_kg: Decimal = Field(gt=0)
    quantity_basis: EnterpriseQuantityBasis = EnterpriseQuantityBasis.BRUTO
    currency: EnterprisePurchaseCurrency | None = None
    unit_price_per_kg: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class EnterprisePurchaseUpdate(BaseModel):
    purchased_on: date | None = None
    quantity_kg: Decimal | None = Field(default=None, gt=0)
    quantity_basis: EnterpriseQuantityBasis | None = None
    currency: EnterprisePurchaseCurrency | None = None
    unit_price_per_kg: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class EnterprisePurchaseRead(IDSchema):
    organization_id: UUID
    farm_id: UUID
    purchased_on: date
    quantity_kg: Decimal
    quantity_basis: EnterpriseQuantityBasis
    currency: EnterprisePurchaseCurrency
    unit_price_per_kg: Decimal
    total_amount: Decimal
    price_bruto_per_kg: Decimal | None = None
    price_neto_per_kg: Decimal | None = None
    notes: str | None = None
    producer_display_name: str | None = None
    farm_name: str | None = None
    created_by_id: UUID | None = None


class EnterpriseOtkupSupplierRow(BaseModel):
    farm_id: UUID
    producer_display_name: str | None = None
    farm_name: str
    assigned_parcels: int = 0
    parcels_with_harvest: int = 0
    # Producer-recorded harvest on assigned parcels (season). None = no harvest events.
    harvest_gross_kg: Decimal | None = None
    harvest_net_kg: Decimal | None = None
    harvest_event_count: int = 0
    last_harvested_on: date | None = None
    currency: EnterprisePurchaseCurrency | None = None
    price_bruto_per_kg: Decimal | None = None
    price_neto_per_kg: Decimal | None = None
    price_notes: str | None = None
    purchase_count: int = 0
    purchased_quantity_kg: Decimal | None = None
    purchased_amount: Decimal | None = None
    last_purchased_on: date | None = None
    # Legacy aliases kept for older clients during transition.
    total_quantity_kg: Decimal | None = None
    total_amount: Decimal | None = None


class EnterpriseOtkupOverview(BaseModel):
    season_year: int
    suppliers: list[EnterpriseOtkupSupplierRow] = Field(default_factory=list)
    purchase_count: int = 0
    total_quantity_kg: Decimal | None = None
    purchased_quantity_kg: Decimal | None = None
    harvest_gross_kg: Decimal | None = None
    harvest_net_kg: Decimal | None = None
    suppliers_with_harvest: int = 0
    totals_by_currency: dict[str, Decimal] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class EnterpriseAlertWatchReview(BaseModel):
    reviewed_at: datetime
    reviewed_by_name: str | None = None
    note: str | None = None


class EnterpriseAlertWatchItem(BaseModel):
    alert_id: UUID
    parcel_id: UUID
    farm_id: UUID
    producer_name: str | None = None
    parcel_name: str
    observation_date: str | None = None
    latest_observation_date: date | None = None
    processed_at: datetime | None = None
    affected_indices: list[str] = Field(default_factory=list)
    anomaly_kinds: list[str] = Field(default_factory=list)
    zone_keys: list[str] = Field(default_factory=list)
    tree_public_ids: list[str] = Field(default_factory=list)
    severity: str
    status: str
    title: str
    summary: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    last_analysis_at: datetime | None = None
    disclaimer: str | None = None
    company_review: EnterpriseAlertWatchReview | None = None
    intelligence_path: str


class EnterpriseAlertWatchPage(BaseModel):
    organization_id: UUID
    open_alerts: int = 0
    alert_count: int = 0
    satellite_anomaly_count: int = 0
    limit: int = 50
    offset: int = 0
    items: list[EnterpriseAlertWatchItem] = Field(default_factory=list)


class EnterpriseAlertReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class EnterpriseAlertReviewRead(BaseModel):
    alert_id: UUID
    organization_id: UUID
    reviewed_at: datetime
    reviewed_by_name: str | None = None
    note: str | None = None
    producer_status: str


FOLLOW_UP_STATUSES = ("open", "in_progress", "completed", "cancelled")


class EnterpriseFollowUpRead(IDSchema):
    organization_id: UUID
    farm_id: UUID | None = None
    parcel_id: UUID | None = None
    alert_id: UUID | None = None
    assignee_user_id: UUID | None = None
    title: str
    body: str | None = None
    status: str
    due_on: date | None = None
    created_by_id: UUID | None = None
    farm_name: str | None = None
    parcel_name: str | None = None
    assignee_name: str | None = None


class EnterpriseFollowUpCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str | None = None
    status: str = "open"
    farm_id: UUID | None = None
    parcel_id: UUID | None = None
    alert_id: UUID | None = None
    assignee_user_id: UUID | None = None
    due_on: date | None = None


class EnterpriseFollowUpUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = None
    status: str | None = None
    farm_id: UUID | None = None
    parcel_id: UUID | None = None
    alert_id: UUID | None = None
    assignee_user_id: UUID | None = None
    due_on: date | None = None


class EnterpriseDataQualityParcel(BaseModel):
    parcel_id: UUID
    parcel_name: str
    farm_id: UUID
    producer_name: str | None = None
    buckets: list[str] = Field(default_factory=list)


class EnterpriseDataQuality(BaseModel):
    organization_id: UUID
    season_year: int
    date_from: date
    date_to: date
    assigned_parcels: int
    usable_scene: int
    cloudy_only: int
    no_scene: int
    insufficient_history: int
    open_alert: int
    incomplete: int
    notes: list[str] = Field(default_factory=list)
    parcels: list[EnterpriseDataQualityParcel] = Field(default_factory=list)
