from __future__ import annotations

import io
import zipfile
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compliance.csv_export import render_report_csv
from app.compliance.definitions import GENERATED_VIA, REPORT_DEFINITIONS
from app.compliance.engines import ComplianceReportEngine
from app.compliance.formatting import format_date
from app.compliance.pdf import render_report_pdf
from app.models.compliance import ComplianceReportDefinition, ComplianceReportRun
from app.models.enums import ComplianceReportFormat, ComplianceReportType
from app.repositories.farm import FarmRepository
from app.schemas.compliance import (
    CompliancePackageRequest,
    ComplianceReportDefinitionRead,
    ComplianceReportFilters,
    ComplianceReportResult,
    ComplianceReportRunRead,
)


DEFAULT_PACKAGE_TYPES = [
    ComplianceReportType.FARM_PROFILE,
    ComplianceReportType.PARCEL_REGISTER,
    ComplianceReportType.PLANT_PROTECTION,
    ComplianceReportType.FERTILIZATION_INPUTS,
    ComplianceReportType.HARVEST_TRACEABILITY,
    ComplianceReportType.FARM_ACTIVITY,
    ComplianceReportType.IRRIGATION_WATER,
]


class ComplianceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.engine = ComplianceReportEngine(db)

    def ensure_definitions(self) -> None:
        existing = {
            (item.type, item.version): item
            for item in self.db.scalars(select(ComplianceReportDefinition)).all()
        }
        for index, spec in enumerate(REPORT_DEFINITIONS):
            key = (spec.type, spec.version)
            current = existing.get(key)
            if current is None:
                self.db.add(
                    ComplianceReportDefinition(
                        type=spec.type,
                        title=spec.title,
                        description=spec.description,
                        data_source=spec.data_source,
                        template=spec.template,
                        version=spec.version,
                        sort_order=spec.sort_order or index,
                        include_in_default_package=spec.include_in_default_package,
                        is_active=True,
                        default_filters={},
                    )
                )
            else:
                current.title = spec.title
                current.description = spec.description
                current.data_source = spec.data_source
                current.template = spec.template
                current.sort_order = spec.sort_order or index
                current.include_in_default_package = spec.include_in_default_package
                current.is_active = True
        self.db.flush()

    def list_definitions(self) -> list[ComplianceReportDefinitionRead]:
        self.ensure_definitions()
        items = self.db.scalars(
            select(ComplianceReportDefinition)
            .where(ComplianceReportDefinition.is_active.is_(True))
            .order_by(ComplianceReportDefinition.sort_order, ComplianceReportDefinition.title)
        ).all()
        return [ComplianceReportDefinitionRead.model_validate(item) for item in items]

    def list_runs(self, owner_id: UUID, *, limit: int = 50) -> list[ComplianceReportRunRead]:
        farm = self._farm(owner_id)
        stmt = (
            select(ComplianceReportRun)
            .where(
                ComplianceReportRun.farm_id == farm.id,
                ComplianceReportRun.format != ComplianceReportFormat.JSON,
                ComplianceReportRun.generated_by_id == owner_id,
            )
            .order_by(ComplianceReportRun.created_at.desc())
            .limit(limit)
        )
        return [ComplianceReportRunRead.model_validate(item) for item in self.db.scalars(stmt).all()]

    def generate_report(
        self,
        owner_id: UUID,
        report_type: ComplianceReportType,
        filters: ComplianceReportFilters,
        *,
        generated_by_id: UUID,
        fmt: ComplianceReportFormat = ComplianceReportFormat.JSON,
        locale: str = "sr",
    ) -> tuple[ComplianceReportResult, bytes | str | None, ComplianceReportRun | None]:
        self.ensure_definitions()
        result = self.engine.build(owner_id, report_type, filters)
        payload: bytes | str | None = None
        if fmt == ComplianceReportFormat.CSV:
            payload = render_report_csv(result)
        elif fmt == ComplianceReportFormat.PDF:
            payload = render_report_pdf(result, locale=locale)
        # JSON preview must not pollute generation history — only exports/packages.
        if fmt == ComplianceReportFormat.JSON:
            return result, payload, None
        run = self._log_run(
            owner_id,
            report_type=report_type,
            title=result.meta.title,
            fmt=fmt,
            filters=filters,
            record_count=result.meta.record_count,
            generated_by_id=generated_by_id,
        )
        return result, payload, run

    def generate_package(
        self,
        owner_id: UUID,
        payload: CompliancePackageRequest,
        *,
        generated_by_id: UUID,
        locale: str = "sr",
    ) -> tuple[bytes, ComplianceReportRun, list[ComplianceReportResult]]:
        self.ensure_definitions()
        types = payload.report_types or list(DEFAULT_PACKAGE_TYPES)
        types = [t for t in types if t != ComplianceReportType.COMPLIANCE_PACKAGE]
        filters = ComplianceReportFilters(
            date_from=payload.date_from,
            date_to=payload.date_to,
            parcel_ids=payload.parcel_ids,
            include_costs=payload.include_costs,
            report_types=types,
        )
        results: list[ComplianceReportResult] = []
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for report_type in types:
                result = self.engine.build(owner_id, report_type, filters)
                results.append(result)
                slug = report_type.value
                archive.writestr(f"{slug}.pdf", render_report_pdf(result, locale=locale))
            lines = [
                "AgroTwin — paket usaglašenosti / audita",
                GENERATED_VIA,
                DISCLAIMER_LINE,
                f"Izveštaji (PDF): {', '.join(t.value for t in types)}",
                f"Period: {format_date(payload.date_from) or '…'} — {format_date(payload.date_to) or '…'}",
            ]
            archive.writestr("README.txt", "\n".join(lines) + "\n")

        run = self._log_run(
            owner_id,
            report_type=ComplianceReportType.COMPLIANCE_PACKAGE,
            title="Paket usaglašenosti / audita",
            fmt=ComplianceReportFormat.ZIP,
            filters=filters,
            record_count=sum(r.meta.record_count for r in results),
            generated_by_id=generated_by_id,
        )
        return buffer.getvalue(), run, results

    def _log_run(
        self,
        owner_id: UUID,
        *,
        report_type: ComplianceReportType,
        title: str,
        fmt: ComplianceReportFormat,
        filters: ComplianceReportFilters,
        record_count: int,
        generated_by_id: UUID,
    ) -> ComplianceReportRun:
        farm = self._farm(owner_id)
        definition = self.db.scalars(
            select(ComplianceReportDefinition).where(
                ComplianceReportDefinition.type == report_type,
                ComplianceReportDefinition.is_active.is_(True),
            )
        ).first()
        run = ComplianceReportRun(
            farm_id=farm.id,
            report_type=report_type,
            title=title,
            format=fmt,
            filters=filters.model_dump(mode="json", exclude_none=True),
            period_from=filters.date_from,
            period_to=filters.date_to,
            parcel_ids=[str(pid) for pid in filters.parcel_ids] if filters.parcel_ids else None,
            record_count=record_count,
            definition_id=definition.id if definition else None,
            definition_version=definition.version if definition else None,
            generated_by_id=generated_by_id,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _farm(self, owner_id: UUID):
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]


DISCLAIMER_LINE = (
    "Izveštaj usaglašenosti AgroTwin. Pripremljen iz evidencije sačuvane u AgroTwin. "
    "Ovaj paket ne sertifikuje gazdinstvo i ne garantuje usklađenost sa GLOBALG.A.P."
)
