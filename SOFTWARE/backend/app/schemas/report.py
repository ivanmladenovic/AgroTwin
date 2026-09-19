from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChangeDirection = Literal["up", "down", "unchanged"]
ChangeTone = Literal["positive", "negative", "neutral"]
KpiValueKind = Literal["count", "money", "mass", "text"]


class YearChange(BaseModel):
    available: bool
    previous: Decimal | None = None
    percent: Decimal | None = None
    direction: ChangeDirection | None = None
    tone: ChangeTone | None = None


class OptionalAmount(BaseModel):
    available: bool
    value: Decimal | None = None


class ReportParcelSummary(BaseModel):
    parcel_id: UUID
    parcel_name: str
    parcel_code: str
    farm_name: str
    year: int
    previous_year: int
    generated_at: datetime
    generated_on: date
    area_hectares: Decimal | None
    currency: str = "EUR"
    available_years: list[int]
    comparison_available: bool


class ReportKpi(BaseModel):
    key: str
    label: str
    available: bool
    kind: KpiValueKind
    value: Decimal | None = None
    change: YearChange


class ReportHealthSummary(BaseModel):
    total_trees: int
    active_trees: int
    healthy: int
    monitoring: int
    issue: int
    unknown: int
    removed: int
    replaced: int
    attention_count: int


class ReportAttentionTree(BaseModel):
    tree_id: UUID
    public_id: str
    row_id: UUID
    row_number: int
    health_status: str
    reason: str
    last_check_on: date | None = None
    days_since_check: int | None = None


class NamedCount(BaseModel):
    id: UUID | None = None
    name: str
    slug: str | None = None
    count: int


class ReportTimelineItem(BaseModel):
    month: int
    performed_on: date
    title: str
    activity_type_name: str
    activity_type_slug: str | None = None


class ReportActivitiesSummary(BaseModel):
    completed_count: int
    planned_count: int
    recorded: bool
    by_type: list[NamedCount]
    timeline: list[ReportTimelineItem]


class ReportPlannedActivity(BaseModel):
    id: UUID
    performed_on: date
    title: str
    activity_type_name: str
    row_number: int | None = None
    tree_public_id: str | None = None


class ReportNamedAmount(BaseModel):
    id: UUID | None = None
    name: str
    slug: str | None = None
    amount: Decimal


class ReportMonthAmount(BaseModel):
    month: int
    amount: Decimal


class ReportFinancialSummary(BaseModel):
    recorded: bool
    annual_cost: OptionalAmount
    previous_year_cost: OptionalAmount
    historical_cost: OptionalAmount
    by_category: list[ReportNamedAmount]
    by_activity: list[ReportNamedAmount]
    monthly: list[ReportMonthAmount]
    cost_per_hectare: OptionalAmount
    cost_per_tree: OptionalAmount
    cost_per_kg: OptionalAmount


class ReportProblemRow(BaseModel):
    row_id: UUID
    row_number: int
    count: int


class ReportProblemSummary(BaseModel):
    recorded: bool
    total: int
    open_count: int
    monitoring_count: int
    resolved_count: int
    by_category: list[NamedCount]
    by_row: list[ReportProblemRow]


class ReportQualityAverage(BaseModel):
    available: bool
    value: Decimal | None = None
    method: str | None = None
    sample_count: int = 0


class ReportQualityCategory(BaseModel):
    category: str
    net_kg: Decimal
    event_count: int


class ReportHarvestQuality(BaseModel):
    recorded: bool
    moisture: ReportQualityAverage
    damaged: ReportQualityAverage
    empty_nuts: ReportQualityAverage
    foreign_material: ReportQualityAverage
    categories: list[ReportQualityCategory] = Field(default_factory=list)


class ReportYieldSummary(BaseModel):
    recorded: bool
    total_kg: Decimal | None = None
    harvest_events: int | None = None
    first_harvest_date: date | None = None
    last_harvest_date: date | None = None
    per_hectare: OptionalAmount
    per_tree: OptionalAmount
    quality: ReportHarvestQuality | None = None
    source: Literal["harvest_event", "activity"] | None = None


class ReportComparisonRow(BaseModel):
    key: str
    label: str
    kind: KpiValueKind
    previous: Decimal | None = None
    current: Decimal | None = None
    change: YearChange


class ReportTrend(BaseModel):
    kind: Literal["monthly_costs"]
    months: list[ReportMonthAmount]


class ParcelAnnualReportRead(BaseModel):
    parcel_summary: ReportParcelSummary
    executive_summary: str
    kpis: list[ReportKpi]
    health_summary: ReportHealthSummary
    trees_requiring_attention: list[ReportAttentionTree]
    trees_requiring_control: list[ReportAttentionTree]
    activities_summary: ReportActivitiesSummary
    planned_activities: list[ReportPlannedActivity]
    financial_summary: ReportFinancialSummary
    problem_summary: ReportProblemSummary
    yield_summary: ReportYieldSummary
    previous_year_comparison: list[ReportComparisonRow]
    yearly_trend: ReportTrend
    extra: dict[str, object] = Field(default_factory=dict)
