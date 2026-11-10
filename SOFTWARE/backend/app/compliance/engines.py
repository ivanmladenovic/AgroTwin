from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.compliance.definitions import DISCLAIMER, REPORT_DEFINITIONS
from app.compliance.formatting import VALUE_LABELS, format_date, format_money_eur, format_quantity
from app.models.activity import Activity
from app.models.enums import ActivitySemanticType, ActivityStatus, ComplianceReportType, WorkTaskStatus
from app.models.farm import Farm
from app.models.harvest import HarvestEvent
from app.models.passport import HarvestLot
from app.models.parcel import Parcel
from app.models.user import User
from app.models.workforce import WorkTask
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.schemas.compliance import (
    ComplianceIssue,
    ComplianceReportFilters,
    ComplianceReportMeta,
    ComplianceReportResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Decimal | float | int | None) -> str:
    return format_money_eur(value)


def _qty(value: Decimal | float | int | None) -> str:
    return format_quantity(value)


def _enum_label(value: Any) -> str:
    if value is None:
        return ""
    raw = value.value if hasattr(value, "value") else str(value)
    return VALUE_LABELS.get(raw, raw)


def _parcel_variety_names(parcel: Parcel) -> str:
    """All recorded varieties on the parcel, comma-separated (not only default)."""
    names: list[str] = []
    seen: set[str] = set()
    for item in parcel.varieties or []:
        if isinstance(item, dict):
            raw = item.get("name")
        else:
            raw = item
        name = str(raw or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    default = (parcel.default_variety or "").strip()
    if default and default.casefold() not in seen:
        names.insert(0, default)
    return ", ".join(names)


class ComplianceReportEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)

    def build(
        self,
        owner_id: UUID,
        report_type: ComplianceReportType,
        filters: ComplianceReportFilters,
    ) -> ComplianceReportResult:
        farm = self._farm(owner_id, filters.farm_id)
        parcel_ids = self._parcel_ids(owner_id, filters.parcel_ids)
        spec = next((item for item in REPORT_DEFINITIONS if item.type == report_type), None)
        title = spec.title if spec else report_type.value

        builders = {
            ComplianceReportType.FARM_PROFILE: self._farm_profile,
            ComplianceReportType.PARCEL_REGISTER: self._parcel_register,
            ComplianceReportType.PLANT_PROTECTION: self._plant_protection,
            ComplianceReportType.FERTILIZATION_INPUTS: self._fertilization,
            ComplianceReportType.HARVEST_TRACEABILITY: self._harvest_traceability,
            ComplianceReportType.FARM_ACTIVITY: self._farm_activity,
            ComplianceReportType.IRRIGATION_WATER: self._irrigation,
        }
        builder = builders.get(report_type)
        if builder is None:
            columns = ["Poruka"]
            rows: list[dict[str, Any]] = [
                {"Poruka": "Ovaj tip izveštaja dostupan je samo u paketu usaglašenosti."}
            ]
            issues: list[ComplianceIssue] = []
        else:
            columns, rows, issues = builder(owner_id, farm, parcel_ids, filters)

        filter_payload = filters.model_dump(mode="json", exclude_none=True)
        return ComplianceReportResult(
            meta=ComplianceReportMeta(
                report_type=report_type,
                title=title,
                farm_name=farm.name,
                farm_id=farm.id,
                period_from=filters.date_from,
                period_to=filters.date_to,
                generated_at=_now(),
                filters=filter_payload,
                record_count=len(rows),
                definition_version=spec.version if spec else "1.0",
                disclaimer=DISCLAIMER,
                issues_count=len(issues),
            ),
            columns=columns,
            rows=rows,
            issues=issues,
        )

    # --- Builders ----------------------------------------------------------------

    def _farm_profile(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        owner = self.db.get(User, farm.owner_id)
        columns = [
            "Gazdinstvo",
            "Proizvođač",
            "Država",
            "Lokacija",
            "Površina (ha)",
            "Broj parcela",
            "Opis",
        ]
        parcels = self.parcels.list_for_owner(owner_id)
        if parcel_ids:
            parcels = [p for p in parcels if p.id in set(parcel_ids)]
        row = {
            "Gazdinstvo": farm.name,
            "Proizvođač": farm.public_producer_name or (owner.full_name if owner else ""),
            "Država": farm.country or "Srbija",
            "Lokacija": farm.location_name or "",
            "Površina (ha)": _qty(farm.area_hectares),
            "Broj parcela": len(parcels),
            "Opis": (farm.description or "")[:500],
        }
        issues: list[ComplianceIssue] = []
        if not row["Lokacija"]:
            issues.append(
                ComplianceIssue(
                    code="missing_location",
                    severity="missing",
                    message="Opšta lokacija gazdinstva nije evidentirana.",
                    field="Lokacija",
                )
            )
        return columns, [row], issues

    def _parcel_register(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        columns = [
            "Parcela",
            "Šifra",
            "Površina (ha)",
            "Kultura",
            "Sorta",
            "Način proizvodnje",
            "Organski obuhvat",
            "Navodnjavanje",
            "Tip navodnjavanja",
            "Godina sadnje",
        ]
        parcels = self.parcels.list_for_owner(owner_id)
        if parcel_ids:
            parcels = [p for p in parcels if p.id in set(parcel_ids)]
        rows: list[dict[str, Any]] = []
        issues: list[ComplianceIssue] = []
        for parcel in parcels:
            variety = _parcel_variety_names(parcel)
            row = {
                "Parcela": parcel.name,
                "Šifra": parcel.code,
                "Površina (ha)": _qty(parcel.area_hectares),
                "Kultura": "Lešnik",
                "Sorta": variety,
                "Način proizvodnje": _enum_label(parcel.production_method),
                "Organski obuhvat": _enum_label(parcel.organic_scope),
                "Navodnjavanje": "Da" if parcel.has_irrigation else "Ne",
                "Tip navodnjavanja": _enum_label(parcel.irrigation_type),
                "Godina sadnje": parcel.default_planting_year or "",
            }
            rows.append(row)
            if filters.crop and filters.crop.lower() not in "lešnik lesnik":
                continue
            if not variety:
                issues.append(
                    ComplianceIssue(
                        code="missing_variety",
                        severity="missing",
                        message=f"Parcela {parcel.name}: sorta nije evidentirana.",
                        field="Sorta",
                    )
                )
        return columns, rows, issues

    def _plant_protection(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        columns = [
            "Gazdinstvo",
            "Parcela",
            "Kultura",
            "Sorta",
            "Datum tretmana",
            "Preparat",
            "Aktivna materija",
            "Svrha",
            "Štetočina / problem",
            "Doza",
            "Količina",
            "Jedinica",
            "Tretirana površina (ha)",
            "Izvršilac",
            "Oprema",
            "Karenca (PHI)",
            "REI",
            "Najbliža berba",
            "Dana do berbe",
            "Trošak (EUR)",
            "Napomene",
        ]
        activities = self._activities(
            owner_id,
            parcel_ids,
            filters,
            semantic=ActivitySemanticType.TREATMENT,
            slugs={"spraying", "disease_treatment"},
        )
        harvests = self._harvests(owner_id, parcel_ids, filters)
        harvests_by_parcel: dict[UUID, list[HarvestEvent]] = {}
        for event in harvests:
            if event.parcel_id is None:
                continue
            harvests_by_parcel.setdefault(event.parcel_id, []).append(event)

        users = {user.id: user for user in self.db.scalars(select(User)).all()}
        parcels = {p.id: p for p in self.parcels.list_for_owner(owner_id)}
        rows: list[dict[str, Any]] = []
        issues: list[ComplianceIssue] = []

        for activity in activities:
            parcel = parcels.get(activity.parcel_id) if activity.parcel_id else None
            variety = _parcel_variety_names(parcel) if parcel else ""
            operator = ""
            if activity.created_by_id and activity.created_by_id in users:
                operator = users[activity.created_by_id].full_name
            if filters.operator and filters.operator.lower() not in operator.lower():
                continue

            line_items = activity.line_items or [{"name": None, "quantity": activity.quantity, "unit": activity.unit, "amount": None}]
            if not line_items:
                line_items = [{"name": None, "quantity": activity.quantity, "unit": activity.unit, "amount": None}]

            nearest_harvest = None
            days_to_harvest = ""
            if activity.parcel_id and activity.parcel_id in harvests_by_parcel:
                after = [
                    h for h in harvests_by_parcel[activity.parcel_id] if h.harvested_on >= activity.performed_on
                ]
                if after:
                    nearest_harvest = min(after, key=lambda h: h.harvested_on)
                    days_to_harvest = str((nearest_harvest.harvested_on - activity.performed_on).days)

            for item in line_items:
                product = (item.get("name") if isinstance(item, dict) else None) or ""
                if filters.product and filters.product.lower() not in product.lower():
                    continue
                if filters.active_substance:
                    # Active substance is not stored — skip row unless empty filter.
                    continue

                qty = item.get("quantity") if isinstance(item, dict) else None
                unit = item.get("unit") if isinstance(item, dict) else None
                amount = item.get("amount") if isinstance(item, dict) else None
                if amount is None and filters.include_costs:
                    amount = sum((c.amount for c in activity.costs), Decimal("0")) if activity.costs else None

                row_issues: list[str] = []
                if not product:
                    row_issues.append("missing_product")
                    issues.append(
                        ComplianceIssue(
                            code="missing_product",
                            severity="missing",
                            message=f"{activity.performed_on}: product/trade name not recorded.",
                            field="product",
                        )
                    )
                if qty in (None, ""):
                    row_issues.append("missing_quantity")
                    issues.append(
                        ComplianceIssue(
                            code="missing_quantity",
                            severity="missing",
                            message=f"{activity.performed_on}: quantity not recorded for treatment.",
                            field="quantity",
                        )
                    )
                row_issues.append("missing_phi")
                issues.append(
                    ComplianceIssue(
                        code="missing_phi",
                        severity="missing",
                        message=f"{activity.performed_on}: PHI not recorded in AgroTwin for this treatment.",
                        field="phi",
                    )
                )
                if days_to_harvest != "" and int(days_to_harvest) <= 14:
                    row_issues.append("treatment_close_to_harvest")
                    issues.append(
                        ComplianceIssue(
                            code="treatment_close_to_harvest",
                            severity="warning",
                            message=(
                                f"{activity.performed_on}: treatment recorded "
                                f"{days_to_harvest} day(s) before next harvest on the same parcel. "
                                "Review PHI on the product label; AgroTwin does not apply legal thresholds."
                            ),
                            field="days_to_harvest",
                        )
                    )

                rows.append(
                    {
                        "Gazdinstvo": farm.name,
                        "Parcela": parcel.name if parcel else "",
                        "Kultura": "Lešnik",
                        "Sorta": variety or "",
                        "Datum tretmana": format_date(activity.performed_on),
                        "Preparat": product,
                        "Aktivna materija": "",
                        "Svrha": activity.activity_type.name if activity.activity_type else activity.title,
                        "Štetočina / problem": (activity.description or "")[:200],
                        "Doza": "",
                        "Količina": _qty(qty if qty is not None else activity.quantity),
                        "Jedinica": unit or activity.unit or "",
                        "Tretirana površina (ha)": _qty(parcel.area_hectares) if parcel else "",
                        "Izvršilac": operator,
                        "Oprema": "",
                        "Karenca (PHI)": "",
                        "REI": "",
                        "Najbliža berba": format_date(nearest_harvest.harvested_on) if nearest_harvest else "",
                        "Dana do berbe": days_to_harvest,
                        "Trošak (EUR)": _money(amount) if filters.include_costs else "",
                        "Napomene": "; ".join(row_issues),
                    }
                )
        return columns, rows, issues

    def _fertilization(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        columns = [
            "Datum",
            "Parcela",
            "Proizvod",
            "Tip proizvoda",
            "Količina",
            "Jedinica",
            "Doza",
            "Izvršilac",
            "Trošak (EUR)",
            "Napomene",
        ]
        activities = self._activities(
            owner_id,
            parcel_ids,
            filters,
            semantic=ActivitySemanticType.FERTILIZATION,
            slugs={"fertilization"},
        )
        users = {user.id: user for user in self.db.scalars(select(User)).all()}
        parcels = {p.id: p for p in self.parcels.list_for_owner(owner_id)}
        rows: list[dict[str, Any]] = []
        issues: list[ComplianceIssue] = []
        for activity in activities:
            parcel = parcels.get(activity.parcel_id) if activity.parcel_id else None
            operator = (
                users[activity.created_by_id].full_name
                if activity.created_by_id and activity.created_by_id in users
                else ""
            )
            if filters.operator and filters.operator.lower() not in operator.lower():
                continue
            items = activity.line_items or [
                {"name": activity.title, "quantity": activity.quantity, "unit": activity.unit, "amount": None}
            ]
            for item in items:
                product = (item.get("name") if isinstance(item, dict) else None) or activity.title
                if filters.product and filters.product.lower() not in str(product).lower():
                    continue
                qty = item.get("quantity") if isinstance(item, dict) else activity.quantity
                unit = item.get("unit") if isinstance(item, dict) else activity.unit
                amount = item.get("amount") if isinstance(item, dict) else None
                if amount is None and filters.include_costs and activity.costs:
                    amount = sum((c.amount for c in activity.costs), Decimal("0"))
                if qty in (None, ""):
                    issues.append(
                        ComplianceIssue(
                            code="missing_quantity",
                            severity="missing",
                            message=f"{activity.performed_on}: fertilization quantity not recorded.",
                            field="quantity",
                        )
                    )
                rows.append(
                    {
                        "Datum": format_date(activity.performed_on),
                        "Parcela": parcel.name if parcel else "",
                        "Proizvod": product,
                        "Tip proizvoda": "Đubrivo",
                        "Količina": _qty(qty),
                        "Jedinica": unit or "",
                        "Doza": "",
                        "Izvršilac": operator,
                        "Trošak (EUR)": _money(amount) if filters.include_costs else "",
                        "Napomene": (activity.notes or activity.description or "")[:300],
                    }
                )
        return columns, rows, issues

    def _harvest_traceability(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        columns = [
            "Broj lota",
            "Lanac sledljivosti",
            "Datum berbe",
            "Parcela",
            "Kultura",
            "Sorta",
            "Količina",
            "Jedinica",
            "Godina proizvodnje",
            "Relevantni tretmani",
            "Relevantno đubrenje",
            "Relevantne aktivnosti",
            "Kupac / destinacija",
            "Status pasoša",
        ]
        lots = self._lots(owner_id, parcel_ids, filters)
        parcels = {p.id: p for p in self.parcels.list_for_owner(owner_id)}
        treatments = self._activities(
            owner_id, parcel_ids, filters, semantic=ActivitySemanticType.TREATMENT, slugs={"spraying", "disease_treatment"}
        )
        ferts = self._activities(
            owner_id, parcel_ids, filters, semantic=ActivitySemanticType.FERTILIZATION, slugs={"fertilization"}
        )
        all_acts = self._activities(owner_id, parcel_ids, filters, semantic=None, slugs=None)

        rows: list[dict[str, Any]] = []
        issues: list[ComplianceIssue] = []
        for lot in lots:
            if filters.crop and filters.crop.lower() not in (lot.crop or "").lower():
                continue
            parcel = parcels.get(lot.parcel_id)
            chain = " → ".join(
                [
                    farm.public_producer_name or farm.name,
                    farm.name,
                    parcel.name if parcel else "parcel",
                    lot.crop,
                    lot.variety or "variety n/a",
                    "production practices",
                    f"berba {format_date(lot.harvest_date)}",
                    "kupac n/a",
                ]
            )
            related_t = [
                f"{format_date(a.performed_on)}:{(a.line_items or [{}])[0].get('name') if a.line_items else a.title}"
                for a in treatments
                if a.parcel_id == lot.parcel_id and a.performed_on <= lot.harvest_date
            ][-5:]
            related_f = [
                f"{format_date(a.performed_on)}:{a.title}"
                for a in ferts
                if a.parcel_id == lot.parcel_id and a.performed_on <= lot.harvest_date
            ][-5:]
            related_a = [
                f"{format_date(a.performed_on)}:{a.title}"
                for a in all_acts
                if a.parcel_id == lot.parcel_id and a.performed_on <= lot.harvest_date
            ][-8:]
            rows.append(
                {
                    "Broj lota": lot.lot_number,
                    "Lanac sledljivosti": chain,
                    "Datum berbe": format_date(lot.harvest_date),
                    "Parcela": parcel.name if parcel else "",
                    "Kultura": lot.crop,
                    "Sorta": lot.variety or "",
                    "Količina": _qty(lot.quantity),
                    "Jedinica": lot.unit,
                    "Godina proizvodnje": lot.harvest_date.year,
                    "Relevantni tretmani": " | ".join(related_t),
                    "Relevantno đubrenje": " | ".join(related_f),
                    "Relevantne aktivnosti": " | ".join(related_a),
                    "Kupac / destinacija": "",
                    "Status pasoša": _enum_label(lot.passport_status),
                }
            )
            if not lot.variety:
                issues.append(
                    ComplianceIssue(
                        code="missing_variety",
                        severity="missing",
                        message=f"Lot {lot.lot_number}: sorta nije evidentirana.",
                        field="Sorta",
                    )
                )

        # Also include harvest events without lots for completeness.
        harvests = self._harvests(owner_id, parcel_ids, filters)
        lot_harvest_ids = {lot.harvest_id for lot in lots}
        for event in harvests:
            if event.id in lot_harvest_ids:
                continue
            parcel = parcels.get(event.parcel_id) if event.parcel_id else None
            rows.append(
                {
                    "Broj lota": "",
                    "Lanac sledljivosti": f"{farm.name} → {parcel.name if parcel else ''} → berba (bez lota)",
                    "Datum berbe": format_date(event.harvested_on),
                    "Parcela": parcel.name if parcel else "",
                    "Kultura": "Lešnik",
                    "Sorta": parcel.default_variety if parcel else "",
                    "Količina": _qty(event.net_quantity or event.gross_quantity),
                    "Jedinica": event.unit,
                    "Godina proizvodnje": event.harvested_on.year,
                    "Relevantni tretmani": "",
                    "Relevantno đubrenje": "",
                    "Relevantne aktivnosti": "",
                    "Kupac / destinacija": "",
                    "Status pasoša": "Bez lota",
                }
            )
            issues.append(
                ComplianceIssue(
                    code="harvest_without_lot",
                    severity="info",
                    message=f"Berba {format_date(event.harvested_on)}: nije kreiran digitalni lot/pasoš.",
                    field="Broj lota",
                )
            )
        return columns, rows, issues

    def _farm_activity(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        columns = ["Datum", "Parcela", "Aktivnost", "Opis", "Radnik", "Sati", "Trošak (EUR)"]
        activities = self._activities(owner_id, parcel_ids, filters, semantic=None, slugs=None)
        if filters.activity_type_id is not None:
            activities = [a for a in activities if a.activity_type_id == filters.activity_type_id]
        parcels = {p.id: p for p in self.parcels.list_for_owner(owner_id)}
        users = {user.id: user for user in self.db.scalars(select(User)).all()}
        tasks = self._work_tasks(owner_id, parcel_ids, filters)
        rows: list[dict[str, Any]] = []
        for activity in activities:
            parcel = parcels.get(activity.parcel_id) if activity.parcel_id else None
            worker = users[activity.created_by_id].full_name if activity.created_by_id in users else ""
            cost = sum((c.amount for c in activity.costs), Decimal("0")) if activity.costs else None
            rows.append(
                {
                    "Datum": format_date(activity.performed_on),
                    "Parcela": parcel.name if parcel else "",
                    "Aktivnost": activity.activity_type.name if activity.activity_type else activity.title,
                    "Opis": activity.title,
                    "Radnik": worker,
                    "Sati": "",
                    "Trošak (EUR)": _money(cost) if filters.include_costs else "",
                }
            )
        for task in tasks:
            if filters.worker_id and task.worker_id != filters.worker_id:
                continue
            worker_name = f"{task.worker.first_name} {task.worker.last_name}".strip() if task.worker else ""
            if filters.operator and filters.operator.lower() not in worker_name.lower():
                continue
            parcel = parcels.get(task.parcel_id)
            rows.append(
                {
                    "Datum": format_date(task.worked_on),
                    "Parcela": parcel.name if parcel else "",
                    "Aktivnost": task.task_type.name if task.task_type else "Radni zadatak",
                    "Opis": task.description or "",
                    "Radnik": worker_name,
                    "Sati": _qty(task.hours),
                    "Trošak (EUR)": _money(task.labor_cost) if filters.include_costs else "",
                }
            )
        rows.sort(key=lambda r: r["Datum"], reverse=True)
        return columns, rows, []

    def _irrigation(
        self,
        owner_id: UUID,
        farm: Farm,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> tuple[list[str], list[dict[str, Any]], list[ComplianceIssue]]:
        columns = [
            "Datum",
            "Parcela",
            "Vrsta zapisa",
            "Tip navodnjavanja",
            "Izvor vode",
            "Opis",
            "Količina",
            "Jedinica",
            "Napomene",
        ]
        parcels = self.parcels.list_for_owner(owner_id)
        if parcel_ids:
            parcels = [p for p in parcels if p.id in set(parcel_ids)]
        rows: list[dict[str, Any]] = []
        for parcel in parcels:
            rows.append(
                {
                    "Datum": "",
                    "Parcela": parcel.name,
                    "Vrsta zapisa": "Profil parcele",
                    "Tip navodnjavanja": _enum_label(parcel.irrigation_type),
                    "Izvor vode": parcel.water_source or "",
                    "Opis": "Profil sistema za navodnjavanje",
                    "Količina": "",
                    "Jedinica": "",
                    "Napomene": (
                        f"Navodnjavanje: {'Da' if parcel.has_irrigation else 'Ne'}; "
                        f"{(parcel.irrigation_notes or '')[:200]}"
                    ),
                }
            )
        activities = self._activities(
            owner_id, parcel_ids, filters, semantic=ActivitySemanticType.IRRIGATION, slugs={"irrigation"}
        )
        parcel_map = {p.id: p for p in parcels}
        for activity in activities:
            parcel = parcel_map.get(activity.parcel_id) if activity.parcel_id else None
            rows.append(
                {
                    "Datum": format_date(activity.performed_on),
                    "Parcela": parcel.name if parcel else "",
                    "Vrsta zapisa": "Aktivnost",
                    "Tip navodnjavanja": _enum_label(parcel.irrigation_type) if parcel else "",
                    "Izvor vode": parcel.water_source if parcel else "",
                    "Opis": activity.title,
                    "Količina": _qty(activity.quantity),
                    "Jedinica": activity.unit or "",
                    "Napomene": (activity.notes or activity.description or "")[:300],
                }
            )
        return columns, rows, []

    # --- Queries -----------------------------------------------------------------

    def _farm(self, owner_id: UUID, farm_id: UUID | None) -> Farm:
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Gazdinstvo nije pronađeno")
        if farm_id is not None:
            for farm in farms:
                if farm.id == farm_id:
                    return farm
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]

    def _parcel_ids(self, owner_id: UUID, requested: list[UUID]) -> list[UUID]:
        if not requested:
            return []
        owned = {p.id for p in self.parcels.list_for_owner(owner_id)}
        return [pid for pid in requested if pid in owned]

    def _activities(
        self,
        owner_id: UUID,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
        *,
        semantic: ActivitySemanticType | None,
        slugs: set[str] | None,
    ) -> list[Activity]:
        stmt = (
            select(Activity)
            .join(Farm, Activity.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id, Activity.status == ActivityStatus.COMPLETED)
            .options(
                selectinload(Activity.activity_type),
                selectinload(Activity.costs),
            )
            .order_by(Activity.performed_on.desc())
        )
        if filters.date_from is not None:
            stmt = stmt.where(Activity.performed_on >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(Activity.performed_on <= filters.date_to)
        if parcel_ids:
            stmt = stmt.where(Activity.parcel_id.in_(parcel_ids))
        activities = list(self.db.scalars(stmt).unique().all())
        if semantic is not None or slugs:
            filtered: list[Activity] = []
            for activity in activities:
                slug = activity.activity_type.slug if activity.activity_type else ""
                if semantic is not None and activity.semantic_type == semantic:
                    filtered.append(activity)
                elif slugs and slug in slugs:
                    filtered.append(activity)
            return filtered
        return activities

    def _harvests(
        self,
        owner_id: UUID,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> list[HarvestEvent]:
        stmt = (
            select(HarvestEvent)
            .join(Farm, HarvestEvent.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .order_by(HarvestEvent.harvested_on.desc())
        )
        if filters.date_from is not None:
            stmt = stmt.where(HarvestEvent.harvested_on >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(HarvestEvent.harvested_on <= filters.date_to)
        if parcel_ids:
            stmt = stmt.where(HarvestEvent.parcel_id.in_(parcel_ids))
        return list(self.db.scalars(stmt).all())

    def _lots(
        self,
        owner_id: UUID,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> list[HarvestLot]:
        stmt = (
            select(HarvestLot)
            .join(Farm, HarvestLot.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(selectinload(HarvestLot.parcel), selectinload(HarvestLot.farm))
            .order_by(HarvestLot.harvest_date.desc())
        )
        if filters.date_from is not None:
            stmt = stmt.where(HarvestLot.harvest_date >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(HarvestLot.harvest_date <= filters.date_to)
        if parcel_ids:
            stmt = stmt.where(HarvestLot.parcel_id.in_(parcel_ids))
        return list(self.db.scalars(stmt).unique().all())

    def _work_tasks(
        self,
        owner_id: UUID,
        parcel_ids: list[UUID],
        filters: ComplianceReportFilters,
    ) -> list[WorkTask]:
        stmt = (
            select(WorkTask)
            .join(Farm, WorkTask.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id, WorkTask.status == WorkTaskStatus.COMPLETED)
            .options(selectinload(WorkTask.worker), selectinload(WorkTask.task_type), selectinload(WorkTask.parcel))
            .order_by(WorkTask.worked_on.desc())
        )
        if filters.date_from is not None:
            stmt = stmt.where(WorkTask.worked_on >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(WorkTask.worked_on <= filters.date_to)
        if parcel_ids:
            stmt = stmt.where(WorkTask.parcel_id.in_(parcel_ids))
        if filters.worker_id is not None:
            stmt = stmt.where(WorkTask.worker_id == filters.worker_id)
        return list(self.db.scalars(stmt).unique().all())
