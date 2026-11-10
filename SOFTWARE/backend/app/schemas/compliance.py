from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.models.enums import ComplianceReportFormat, ComplianceReportType
from app.schemas.common import IDSchema, ORMModel


class ComplianceReportDefinitionRead(IDSchema):
    type: ComplianceReportType
    title: str
    description: str | None
    data_source: str
    template: str
    version: str
    default_filters: dict[str, Any]
    sort_order: int
    is_active: bool
    include_in_default_package: bool


class ComplianceReportFilters(ORMModel):
    date_from: date | None = None
    date_to: date | None = None
    parcel_ids: list[UUID] = Field(default_factory=list)
    farm_id: UUID | None = None
    crop: str | None = None
    product: str | None = None
    active_substance: str | None = None
    operator: str | None = None
    activity_type_id: UUID | None = None
    worker_id: UUID | None = None
    include_costs: bool = True
    report_types: list[ComplianceReportType] = Field(default_factory=list)


class ComplianceIssue(ORMModel):
    code: str
    severity: str  # info | warning | missing
    message: str
    field: str | None = None


class ComplianceReportMeta(ORMModel):
    report_type: ComplianceReportType
    title: str
    farm_name: str
    farm_id: UUID
    period_from: date | None = None
    period_to: date | None = None
    generated_at: datetime
    filters: dict[str, Any]
    record_count: int
    definition_version: str = "1.0"
    disclaimer: str
    issues_count: int = 0


class ComplianceReportResult(ORMModel):
    meta: ComplianceReportMeta
    columns: list[str]
    rows: list[dict[str, Any]]
    issues: list[ComplianceIssue] = Field(default_factory=list)


class ComplianceReportRunRead(IDSchema):
    farm_id: UUID
    report_type: ComplianceReportType
    title: str
    format: ComplianceReportFormat
    filters: dict[str, Any]
    period_from: date | None
    period_to: date | None
    parcel_ids: list[Any] | None
    record_count: int
    definition_id: UUID | None
    definition_version: str | None
    generated_by_id: UUID | None
    notes: str | None = None


class CompliancePackageRequest(ORMModel):
    date_from: date | None = None
    date_to: date | None = None
    parcel_ids: list[UUID] = Field(default_factory=list)
    report_types: list[ComplianceReportType] = Field(default_factory=list)
    include_costs: bool = True
    as_zip: bool = True
