from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, DBSession, RequestLocale
from app.models.enums import ComplianceReportFormat, ComplianceReportType
from app.schemas.compliance import (
    CompliancePackageRequest,
    ComplianceReportDefinitionRead,
    ComplianceReportFilters,
    ComplianceReportResult,
    ComplianceReportRunRead,
)
from app.services.compliance import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/definitions", response_model=list[ComplianceReportDefinitionRead])
def list_definitions(current_user: CurrentUser, db: DBSession) -> list[ComplianceReportDefinitionRead]:
    return ComplianceService(db).list_definitions()


@router.get("/runs", response_model=list[ComplianceReportRunRead])
def list_runs(current_user: CurrentUser, db: DBSession, limit: int = Query(default=50, ge=1, le=200)) -> list[ComplianceReportRunRead]:
    return ComplianceService(db).list_runs(current_user.id, limit=limit)


@router.get("/reports/{report_type}", response_model=ComplianceReportResult)
def get_report_json(
    report_type: ComplianceReportType,
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = None,
    date_to: date | None = None,
    parcel_id: UUID | None = None,
    parcel_ids: list[UUID] | None = Query(default=None),
    crop: str | None = None,
    product: str | None = None,
    active_substance: str | None = None,
    operator: str | None = None,
    activity_type_id: UUID | None = None,
    worker_id: UUID | None = None,
    include_costs: bool = True,
) -> ComplianceReportResult:
    filters = _filters(
        date_from=date_from,
        date_to=date_to,
        parcel_id=parcel_id,
        parcel_ids=parcel_ids,
        crop=crop,
        product=product,
        active_substance=active_substance,
        operator=operator,
        activity_type_id=activity_type_id,
        worker_id=worker_id,
        include_costs=include_costs,
    )
    result, _, _ = ComplianceService(db).generate_report(
        current_user.id,
        report_type,
        filters,
        generated_by_id=current_user.id,
        fmt=ComplianceReportFormat.JSON,
    )
    return result


@router.get("/reports/{report_type}/export.csv")
def get_report_csv(
    report_type: ComplianceReportType,
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = None,
    date_to: date | None = None,
    parcel_id: UUID | None = None,
    parcel_ids: list[UUID] | None = Query(default=None),
    crop: str | None = None,
    product: str | None = None,
    operator: str | None = None,
    activity_type_id: UUID | None = None,
    worker_id: UUID | None = None,
    include_costs: bool = True,
) -> Response:
    filters = _filters(
        date_from=date_from,
        date_to=date_to,
        parcel_id=parcel_id,
        parcel_ids=parcel_ids,
        crop=crop,
        product=product,
        operator=operator,
        activity_type_id=activity_type_id,
        worker_id=worker_id,
        include_costs=include_costs,
    )
    _, payload, _ = ComplianceService(db).generate_report(
        current_user.id,
        report_type,
        filters,
        generated_by_id=current_user.id,
        fmt=ComplianceReportFormat.CSV,
    )
    filename = f"agrotwin-{report_type.value}.csv"
    return Response(
        content=payload or "",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{report_type}/export.pdf")
def get_report_pdf(
    report_type: ComplianceReportType,
    current_user: CurrentUser,
    db: DBSession,
    locale: RequestLocale,
    date_from: date | None = None,
    date_to: date | None = None,
    parcel_id: UUID | None = None,
    parcel_ids: list[UUID] | None = Query(default=None),
    crop: str | None = None,
    product: str | None = None,
    operator: str | None = None,
    activity_type_id: UUID | None = None,
    worker_id: UUID | None = None,
    include_costs: bool = True,
) -> Response:
    filters = _filters(
        date_from=date_from,
        date_to=date_to,
        parcel_id=parcel_id,
        parcel_ids=parcel_ids,
        crop=crop,
        product=product,
        operator=operator,
        activity_type_id=activity_type_id,
        worker_id=worker_id,
        include_costs=include_costs,
    )
    _, payload, _ = ComplianceService(db).generate_report(
        current_user.id,
        report_type,
        filters,
        generated_by_id=current_user.id,
        fmt=ComplianceReportFormat.PDF,
        locale=locale,
    )
    filename = f"agrotwin-{report_type.value}.pdf"
    return Response(
        content=payload or b"",
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/package")
def create_compliance_package(
    payload: CompliancePackageRequest,
    current_user: CurrentUser,
    db: DBSession,
    locale: RequestLocale,
) -> Response:
    raw, run, results = ComplianceService(db).generate_package(
        current_user.id, payload, generated_by_id=current_user.id, locale=locale
    )
    if not payload.as_zip:
        return JSONResponse(
            {
                "run_id": str(run.id),
                "record_count": run.record_count,
                "reports": [item.model_dump(mode="json") for item in results],
            }
        )
    filename = f"agrotwin-compliance-package-{run.created_at.date().isoformat()}.zip"
    return Response(
        content=raw,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Compliance-Run-Id": str(run.id),
            "X-Record-Count": str(run.record_count),
        },
    )


def _filters(
    *,
    date_from: date | None,
    date_to: date | None,
    parcel_id: UUID | None,
    parcel_ids: list[UUID] | None,
    crop: str | None = None,
    product: str | None = None,
    active_substance: str | None = None,
    operator: str | None = None,
    activity_type_id: UUID | None = None,
    worker_id: UUID | None = None,
    include_costs: bool = True,
) -> ComplianceReportFilters:
    ids = list(parcel_ids or [])
    if parcel_id is not None and parcel_id not in ids:
        ids.append(parcel_id)
    return ComplianceReportFilters(
        date_from=date_from,
        date_to=date_to,
        parcel_ids=ids,
        crop=crop,
        product=product,
        active_substance=active_substance,
        operator=operator,
        activity_type_id=activity_type_id,
        worker_id=worker_id,
        include_costs=include_costs,
    )
