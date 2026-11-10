"""Enterprise orchard monitoring / attention-center aggregation (read-only)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.context.weather_agg import FROST_DAY_C
from app.enterprise.access import EnterpriseAccess
from app.models.activity import Activity
from app.models.disease import DiseaseCase
from app.models.enums import (
    ActivitySemanticType,
    DiseaseCaseStatus,
    DiseaseSeverity,
    ObservationCategory,
    ObservationStatus,
    PlanningItemStatus,
    PlanningScopeType,
)
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.planning import PlanningPlan, PlanningPlanItem, PlanningSeason
from app.models.soil_lab import SoilLabAnalysis
from app.models.user import User
from app.models.weather import WeatherForecastCache
from app.schemas.enterprise import (
    EnterpriseAttentionItem,
    EnterpriseDataQualityItem,
    EnterpriseMetricAvailability,
    EnterpriseMonitoringActivityItem,
    EnterpriseMonitoringCenter,
    EnterpriseMonitoringFiltersMeta,
    EnterpriseMonitoringKpis,
    EnterpriseMonitoringObservationItem,
    EnterpriseMonitoringPlanItem,
    EnterpriseWeatherSignal,
)
from app.services.enterprise import EnterpriseService
from app.services.weather_calc import DEFAULT_TIMEZONE

# Documented freshness policy: lab older than 3 years is stale (not missing).
SOIL_LAB_STALE_DAYS = 365 * 3
# Forecast look-ahead for environmental signals (cached Yr data only).
WEATHER_SIGNAL_DAYS = 5
HEAT_SIGNAL_C = 35.0  # higher than context HOT_DAY_C; used only as forecast attention threshold


_OPEN_OBSERVATION_STATUSES = {
    ObservationStatus.NEW,
    ObservationStatus.MONITORING,
    ObservationStatus.CONFIRMED,
    ObservationStatus.UNKNOWN,
}
_CLOSED_OBSERVATION_STATUSES = {ObservationStatus.RESOLVED, ObservationStatus.REJECTED}
_OPEN_DISEASE_STATUSES = {DiseaseCaseStatus.OPEN, DiseaseCaseStatus.MONITORING}
_ACTIVE_PLAN_STATUSES = {
    PlanningItemStatus.PLANNED,
    PlanningItemStatus.MONITOR,
    PlanningItemStatus.OBSERVED,
    PlanningItemStatus.NEEDS_REVIEW,
    PlanningItemStatus.APPROVED,
}
_DONE_PLAN_STATUSES = {PlanningItemStatus.COMPLETED, PlanningItemStatus.CANCELLED}

_SEVERITY_RANK = {
    DiseaseSeverity.CRITICAL: 0,
    DiseaseSeverity.HIGH: 1,
    DiseaseSeverity.MEDIUM: 2,
    DiseaseSeverity.LOW: 3,
}

_CATEGORY_LABELS = {
    "reported_problem": "Prijavljen problem",
    "suspected_disease_pest": "Sumnja na bolest / štetočinu",
    "weather_damage": "Šteta od vremena",
    "irrigation_soil": "Navodnjavanje / zemljište",
    "follow_up": "Potreban nastavak",
    "incomplete_data": "Nepotpuni podaci",
    "stale_data": "Zastareli podaci",
    "open_disease_case": "Otvoren slučaj bolesti",
    "awaiting_review": "Čeka pregled",
    "overdue_plan": "Zakasnao plan",
    "due_soon_plan": "Plan uskoro",
    "weather_forecast": "Vremenska prognoza",
    "other_observation": "Zapažanje",
}


def _enum_val(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


class EnterpriseMonitoringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.access = EnterpriseAccess(db)
        self.enterprise = EnterpriseService(db)

    def monitoring_center(
        self,
        user: User,
        organization_id: UUID,
        *,
        year: int | None = None,
        farm_id: UUID | None = None,
        parcel_id: UUID | None = None,
        category: str | None = None,
        review_status: str | None = None,
        severity: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> EnterpriseMonitoringCenter:
        self.access.require_reader(user, organization_id)
        today = date.today()
        season_year = year or today.year
        period_from = date_from or date(season_year, 1, 1)
        period_to = date_to or min(today, date(season_year, 12, 31))
        if period_from > period_to:
            period_from, period_to = period_to, period_from

        assigned = set(self.access.assigned_parcel_ids(organization_id))
        notes: list[str] = []
        if not assigned:
            notes.append("Nema dodeljenih parcela — monitoring je prazan.")
            return self._empty(season_year, period_from, period_to, notes)

        if parcel_id is not None:
            if parcel_id not in assigned:
                return self._empty(
                    season_year,
                    period_from,
                    period_to,
                    ["Izabrana parcela nije u dodeljenom obuhvatu."],
                )
            selected_ids = {parcel_id}
        else:
            selected_ids = set(assigned)

        parcels = list(
            self.db.scalars(select(Parcel).where(Parcel.id.in_(selected_ids))).all()
        )
        if farm_id is not None:
            parcels = [p for p in parcels if p.farm_id == farm_id]
            selected_ids = {p.id for p in parcels}

        if not selected_ids:
            notes.append("Nijedna parcela ne odgovara filterima.")
            return self._empty(season_year, period_from, period_to, notes)

        farm_ids = {p.farm_id for p in parcels}
        farms = {
            f.id: f
            for f in self.db.scalars(select(Farm).where(Farm.id.in_(farm_ids))).all()
        }
        parcel_meta: dict[UUID, tuple[Parcel, Farm | None, str | None]] = {}
        for parcel in parcels:
            farm = farms.get(parcel.farm_id)
            display, _, _ = self.enterprise._producer_display(farm)
            parcel_meta[parcel.id] = (parcel, farm, display)

        # --- Observations / problems (Activity journal) ---
        activities = list(
            self.db.scalars(
                select(Activity)
                .options(joinedload(Activity.activity_type))
                .where(
                    Activity.parcel_id.in_(selected_ids),
                    Activity.performed_on >= period_from,
                    Activity.performed_on <= period_to,
                )
                .order_by(Activity.performed_on.desc())
            ).unique().all()
        )

        observation_rows: list[EnterpriseMonitoringObservationItem] = []
        open_problem_ids: set[UUID] = set()
        new_observation_count = 0
        attention: list[EnterpriseAttentionItem] = []
        attention_parcel_ids: set[UUID] = set()

        for act in activities:
            if act.parcel_id is None:
                continue
            meta = parcel_meta.get(act.parcel_id)
            if meta is None:
                continue
            parcel, farm, display = meta
            semantic = act.semantic_type
            is_obs = semantic in (
                ActivitySemanticType.OBSERVATION,
                ActivitySemanticType.PROBLEM,
                ActivitySemanticType.MONITORING,
            )
            if is_obs:
                new_observation_count += 1
                obs_status = act.observation_status
                is_open = (
                    semantic == ActivitySemanticType.PROBLEM
                    and obs_status not in _CLOSED_OBSERVATION_STATUSES
                ) or (
                    obs_status in _OPEN_OBSERVATION_STATUSES
                    if obs_status is not None
                    else semantic == ActivitySemanticType.PROBLEM
                )
                if is_open and semantic in (
                    ActivitySemanticType.PROBLEM,
                    ActivitySemanticType.OBSERVATION,
                ):
                    open_problem_ids.add(act.id)

                cat = self._observation_category_key(act)
                item = EnterpriseMonitoringObservationItem(
                    id=act.id,
                    parcel_id=parcel.id,
                    farm_id=parcel.farm_id,
                    parcel_name=parcel.name,
                    farm_name=farm.name if farm else "—",
                    producer_display_name=display,
                    performed_on=act.performed_on,
                    title=act.title,
                    description=act.description,
                    semantic_type=_enum_val(semantic),
                    observation_category=_enum_val(act.observation_category),
                    observation_severity=_enum_val(act.observation_severity),
                    observation_status=_enum_val(obs_status),
                    activity_status=_enum_val(act.status) or "unknown",
                    activity_type_name=act.activity_type.name if act.activity_type else None,
                    source="producer",
                    photo_url=None,
                    follow_up_of_id=act.follow_up_of_id,
                    row_id=act.row_id,
                    tree_id=act.tree_id,
                    category=cat,
                )
                if self._match_filters(
                    category=category,
                    review_status=review_status,
                    severity=severity,
                    item_category=cat,
                    item_status=_enum_val(obs_status),
                    item_severity=_enum_val(act.observation_severity),
                ):
                    observation_rows.append(item)

                if is_open and self._match_filters(
                    category=category,
                    review_status=review_status,
                    severity=severity,
                    item_category=cat,
                    item_status=_enum_val(obs_status),
                    item_severity=_enum_val(act.observation_severity),
                ):
                    reason = self._observation_reason(act)
                    attention.append(
                        self._attention_from_observation(item, reason=reason)
                    )
                    attention_parcel_ids.add(parcel.id)

        # --- Disease cases (separate track) ---
        disease_cases = list(
            self.db.scalars(
                select(DiseaseCase).where(
                    DiseaseCase.parcel_id.in_(selected_ids),
                    DiseaseCase.detected_on >= period_from,
                    DiseaseCase.detected_on <= period_to,
                )
            ).all()
        )
        for case in disease_cases:
            meta = parcel_meta.get(case.parcel_id)
            if meta is None:
                continue
            parcel, farm, display = meta
            is_open = case.status in _OPEN_DISEASE_STATUSES
            if is_open:
                open_problem_ids.add(case.id)
            cat = "open_disease_case" if is_open else "suspected_disease_pest"
            if case.category and case.category.value in ("disease", "pest"):
                cat = "suspected_disease_pest" if not is_open else "open_disease_case"
            obs_item = EnterpriseMonitoringObservationItem(
                id=case.id,
                parcel_id=parcel.id,
                farm_id=parcel.farm_id,
                parcel_name=parcel.name,
                farm_name=farm.name if farm else "—",
                producer_display_name=display,
                performed_on=case.detected_on,
                title=case.title,
                description=case.description,
                semantic_type="disease_case",
                observation_category=_enum_val(case.category),
                observation_severity=_enum_val(case.severity),
                observation_status=_enum_val(case.status),
                activity_status=_enum_val(case.status) or "unknown",
                activity_type_name="Slučaj bolesti",
                source="producer",
                photo_url=None,
                follow_up_of_id=None,
                row_id=case.row_id,
                tree_id=case.tree_id,
                category=cat,
            )
            if self._match_filters(
                category=category,
                review_status=review_status,
                severity=severity,
                item_category=cat,
                item_status=_enum_val(case.status),
                item_severity=_enum_val(case.severity),
            ):
                observation_rows.append(obs_item)
            if is_open and self._match_filters(
                category=category,
                review_status=review_status,
                severity=severity,
                item_category=cat,
                item_status=_enum_val(case.status),
                item_severity=_enum_val(case.severity),
            ):
                attention.append(
                    EnterpriseAttentionItem(
                        id=f"disease:{case.id}",
                        category=cat,
                        category_label=_CATEGORY_LABELS.get(cat, cat),
                        parcel_id=parcel.id,
                        farm_id=parcel.farm_id,
                        parcel_name=parcel.name,
                        farm_name=farm.name if farm else "—",
                        producer_display_name=display,
                        event_date=case.detected_on,
                        title=case.title,
                        description=case.description,
                        source="producer",
                        review_status=_enum_val(case.status),
                        severity=_enum_val(case.severity),
                        reason=(
                            f"Otvoren slučaj bolesti/štetočine (status: {case.status.value}, "
                            f"težina: {case.severity.value}). Nije potvrđena dijagnoza van evidentiranog zapisa."
                        ),
                        source_type="disease_case",
                        source_id=case.id,
                        priority_rank=self._priority_rank(
                            severity=case.severity,
                            awaiting_review=case.status == DiseaseCaseStatus.OPEN,
                            confirmed_unresolved=case.status
                            == DiseaseCaseStatus.MONITORING,
                            overdue=False,
                            data_gap=False,
                        ),
                    )
                )
                attention_parcel_ids.add(parcel.id)

        # --- Recorded field activities (non-observation diary) ---
        activity_feed: list[EnterpriseMonitoringActivityItem] = []
        for act in activities:
            if act.parcel_id is None:
                continue
            if act.semantic_type in (
                ActivitySemanticType.OBSERVATION,
                ActivitySemanticType.PROBLEM,
                ActivitySemanticType.MONITORING,
            ):
                continue
            meta = parcel_meta.get(act.parcel_id)
            if meta is None:
                continue
            parcel, farm, display = meta
            activity_feed.append(
                EnterpriseMonitoringActivityItem(
                    id=act.id,
                    parcel_id=parcel.id,
                    farm_id=parcel.farm_id,
                    parcel_name=parcel.name,
                    farm_name=farm.name if farm else "—",
                    producer_display_name=display,
                    performed_on=act.performed_on,
                    title=act.title,
                    description=act.description,
                    semantic_type=_enum_val(act.semantic_type),
                    activity_type_name=act.activity_type.name if act.activity_type else None,
                    status=_enum_val(act.status) or "unknown",
                    source="producer",
                )
            )

        # --- Planning tasks with due dates ---
        plan_items = self._load_plan_items(selected_ids, season_year)
        plan_feed: list[EnterpriseMonitoringPlanItem] = []
        overdue_plan_count = 0
        for item, season_parcel_id in plan_items:
            parcel_id_eff = season_parcel_id
            if item.scope_type == PlanningScopeType.PARCEL:
                parcel_id_eff = item.scope_id
            meta = parcel_meta.get(parcel_id_eff)
            if meta is None:
                continue
            parcel, farm, display = meta
            due = item.planned_date_to or item.planned_date_from
            status = item.status
            bucket = "planned"
            if status in _DONE_PLAN_STATUSES:
                bucket = "completed" if status == PlanningItemStatus.COMPLETED else "cancelled"
            elif due is not None and due < today and status in _ACTIVE_PLAN_STATUSES:
                bucket = "overdue"
                overdue_plan_count += 1
            elif due is not None and due <= today + timedelta(days=7) and status in _ACTIVE_PLAN_STATUSES:
                bucket = "due_soon"

            plan_row = EnterpriseMonitoringPlanItem(
                id=item.id,
                parcel_id=parcel.id,
                farm_id=parcel.farm_id,
                parcel_name=parcel.name,
                farm_name=farm.name if farm else "—",
                producer_display_name=display,
                title=item.title,
                description=item.description,
                planned_date_from=item.planned_date_from,
                planned_date_to=item.planned_date_to,
                status=_enum_val(status) or "unknown",
                priority_level=_enum_val(item.priority_level),
                item_kind=_enum_val(item.item_kind),
                bucket=bucket,
                source=_enum_val(item.source) or "user",
            )
            plan_feed.append(plan_row)

            if bucket in ("overdue", "due_soon") and self._match_filters(
                category=category,
                review_status=review_status,
                severity=severity,
                item_category="overdue_plan" if bucket == "overdue" else "due_soon_plan",
                item_status=_enum_val(status),
                item_severity=None,
            ):
                cat = "overdue_plan" if bucket == "overdue" else "due_soon_plan"
                attention.append(
                    EnterpriseAttentionItem(
                        id=f"plan:{item.id}",
                        category=cat,
                        category_label=_CATEGORY_LABELS.get(cat, cat),
                        parcel_id=parcel.id,
                        farm_id=parcel.farm_id,
                        parcel_name=parcel.name,
                        farm_name=farm.name if farm else "—",
                        producer_display_name=display,
                        event_date=due or today,
                        title=item.title,
                        description=item.description,
                        source="planning",
                        review_status=_enum_val(status),
                        severity=None,
                        reason=(
                            f"Planirana stavka je {('zakasnela' if bucket == 'overdue' else 'uskoro na redu')} "
                            f"(rok: {due.isoformat() if due else 'nije zadan'}). "
                            "Nedostajući dnevnički unos nije tretiran kao nedovršena aktivnost."
                        ),
                        source_type="planning_item",
                        source_id=item.id,
                        priority_rank=self._priority_rank(
                            severity=None,
                            awaiting_review=False,
                            confirmed_unresolved=False,
                            overdue=bucket == "overdue",
                            data_gap=False,
                        ),
                    )
                )
                attention_parcel_ids.add(parcel.id)

        # --- Data quality ---
        data_quality: list[EnterpriseDataQualityItem] = []
        incomplete_count = 0
        for parcel in parcels:
            farm = farms.get(parcel.farm_id)
            display, _, _ = self.enterprise._producer_display(farm)
            missing = self.enterprise._missing_fields(parcel)
            if missing:
                incomplete_count += 1
                if category in (None, "", "incomplete_data"):
                    data_quality.append(
                        EnterpriseDataQualityItem(
                            parcel_id=parcel.id,
                            farm_id=parcel.farm_id,
                            parcel_name=parcel.name,
                            farm_name=farm.name if farm else "—",
                            producer_display_name=display,
                            kind="incomplete",
                            detail=", ".join(missing),
                            missing_fields=missing,
                            completeness_score=self._score(parcel, missing),
                        )
                    )
                    attention.append(
                        EnterpriseAttentionItem(
                            id=f"incomplete:{parcel.id}",
                            category="incomplete_data",
                            category_label=_CATEGORY_LABELS["incomplete_data"],
                            parcel_id=parcel.id,
                            farm_id=parcel.farm_id,
                            parcel_name=parcel.name,
                            farm_name=farm.name if farm else "—",
                            producer_display_name=display,
                            event_date=today,
                            title=f"Nepotpuni podaci: {parcel.name}",
                            description=f"Nedostaje: {', '.join(missing)}",
                            source="completeness",
                            review_status=None,
                            severity=None,
                            reason="Nedostaju polja potrebna za pouzdan monitoring / planiranje.",
                            source_type="parcel",
                            source_id=parcel.id,
                            priority_rank=self._priority_rank(
                                severity=None,
                                awaiting_review=False,
                                confirmed_unresolved=False,
                                overdue=False,
                                data_gap=True,
                            ),
                        )
                    )
                    attention_parcel_ids.add(parcel.id)

        # --- Stale soil lab ---
        stale_count = 0
        latest_lab = self._latest_soil_lab_by_parcel(selected_ids)
        cutoff = today - timedelta(days=SOIL_LAB_STALE_DAYS)
        for parcel in parcels:
            lab_date = latest_lab.get(parcel.id)
            if lab_date is None or lab_date >= cutoff:
                continue
            stale_count += 1
            farm = farms.get(parcel.farm_id)
            display, _, _ = self.enterprise._producer_display(farm)
            if category in (None, "", "stale_data"):
                data_quality.append(
                    EnterpriseDataQualityItem(
                        parcel_id=parcel.id,
                        farm_id=parcel.farm_id,
                        parcel_name=parcel.name,
                        farm_name=farm.name if farm else "—",
                        producer_display_name=display,
                        kind="stale_soil_lab",
                        detail=(
                            f"Poslednja lab analiza zemljišta: {lab_date.isoformat()} "
                            f"(prag: {SOIL_LAB_STALE_DAYS} dana)."
                        ),
                        missing_fields=[],
                        completeness_score=None,
                        reference_date=lab_date,
                    )
                )
                attention.append(
                    EnterpriseAttentionItem(
                        id=f"stale-soil:{parcel.id}",
                        category="stale_data",
                        category_label=_CATEGORY_LABELS["stale_data"],
                        parcel_id=parcel.id,
                        farm_id=parcel.farm_id,
                        parcel_name=parcel.name,
                        farm_name=farm.name if farm else "—",
                        producer_display_name=display,
                        event_date=lab_date,
                        title="Zastarela lab analiza zemljišta",
                        description=(
                            f"Poslednji uzorak: {lab_date.isoformat()}. "
                            f"Politika: starije od {SOIL_LAB_STALE_DAYS} dana."
                        ),
                        source="soil_lab",
                        review_status=None,
                        severity=None,
                        reason="Postoji lab zapis, ali je stariji od dokumentovanog praga svežine.",
                        source_type="parcel",
                        source_id=parcel.id,
                        priority_rank=self._priority_rank(
                            severity=None,
                            awaiting_review=False,
                            confirmed_unresolved=False,
                            overdue=False,
                            data_gap=True,
                        ),
                    )
                )
                attention_parcel_ids.add(parcel.id)

        # --- Weather forecast signals (cache only; no live fetch) ---
        weather_signals, weather_meta = self._weather_signals(
            parcel_meta=parcel_meta,
            selected_ids=selected_ids,
            category=category,
            today=today,
        )
        for signal in weather_signals:
            if signal.signal_kind.startswith("forecast_"):
                attention.append(
                    EnterpriseAttentionItem(
                        id=f"weather:{signal.parcel_id}:{signal.signal_kind}",
                        category="weather_forecast",
                        category_label=_CATEGORY_LABELS["weather_forecast"],
                        parcel_id=signal.parcel_id,
                        farm_id=signal.farm_id,
                        parcel_name=signal.parcel_name,
                        farm_name=signal.farm_name,
                        producer_display_name=signal.producer_display_name,
                        event_date=signal.period_start or today,
                        title=signal.title,
                        description=signal.detail,
                        source="weather_forecast",
                        review_status=None,
                        severity=None,
                        reason=signal.reason,
                        source_type="weather_cache",
                        source_id=signal.parcel_id,
                        priority_rank=40,
                    )
                )
                # Forecast alone does not mark parcel as "needs inspection" unless paired —
                # still count for attention list but only add to parcels_for_review if producer
                # also has matching weather_damage observation in period.
                has_weather_obs = any(
                    o.parcel_id == signal.parcel_id
                    and o.observation_category == "weather_damage"
                    for o in observation_rows
                )
                if has_weather_obs:
                    attention_parcel_ids.add(signal.parcel_id)

        attention.sort(
            key=lambda row: (
                row.priority_rank,
                -(row.event_date.toordinal() if row.event_date else 0),
            )
        )

        # Filter attention by category/status/severity if set
        if category:
            attention = [a for a in attention if a.category == category]
        if review_status:
            attention = [
                a
                for a in attention
                if (a.review_status or "") == review_status
            ]
        if severity:
            attention = [a for a in attention if (a.severity or "") == severity]

        # Recompute attention parcels after filters for KPI consistency with focused list
        filtered_attention_parcels = {a.parcel_id for a in attention}

        kpis = EnterpriseMonitoringKpis(
            open_problems=EnterpriseMetricAvailability(
                available=True,
                value=len(open_problem_ids),
            ),
            new_observations=EnterpriseMetricAvailability(
                available=True,
                value=new_observation_count,
            ),
            pending_plan_tasks=EnterpriseMetricAvailability(
                available=True,
                value=overdue_plan_count,
                note="Samo planirane stavke sa datumom i statusom koji nije completed/cancelled.",
            ),
            parcels_for_review=EnterpriseMetricAvailability(
                available=True,
                value=len(filtered_attention_parcels),
            ),
            incomplete_data=EnterpriseMetricAvailability(
                available=True,
                value=incomplete_count,
            ),
            stale_data=EnterpriseMetricAvailability(
                available=True,
                value=stale_count,
                note=f"Lab analiza starija od {SOIL_LAB_STALE_DAYS} dana.",
            ),
        )

        filter_options = self._filter_options(parcel_meta)

        return EnterpriseMonitoringCenter(
            season_year=season_year,
            period_from=period_from,
            period_to=period_to,
            kpis=kpis,
            attention_items=attention[:100],
            observations=observation_rows[:100],
            activities=activity_feed[:100],
            plan_items=plan_feed[:100],
            weather_signals=weather_signals[:50],
            data_quality=data_quality[:100],
            weather=weather_meta,
            filters=filter_options,
            notes=notes,
            category_labels=_CATEGORY_LABELS,
        )

    def count_parcels_with_issues(self, organization_id: UUID) -> int:
        """Parcels with open disease cases or open observation/problem journal entries."""
        parcel_ids = self.access.assigned_parcel_ids(organization_id)
        if not parcel_ids:
            return 0
        disease_parcels = set(
            self.db.scalars(
                select(DiseaseCase.parcel_id).where(
                    DiseaseCase.parcel_id.in_(parcel_ids),
                    DiseaseCase.status.in_(list(_OPEN_DISEASE_STATUSES)),
                )
            ).all()
        )
        obs_parcels = set(
            self.db.scalars(
                select(Activity.parcel_id).where(
                    Activity.parcel_id.in_(parcel_ids),
                    Activity.semantic_type.in_(
                        [ActivitySemanticType.OBSERVATION, ActivitySemanticType.PROBLEM]
                    ),
                    or_(
                        Activity.observation_status.in_(list(_OPEN_OBSERVATION_STATUSES)),
                        and_(
                            Activity.semantic_type == ActivitySemanticType.PROBLEM,
                            or_(
                                Activity.observation_status.is_(None),
                                Activity.observation_status.notin_(
                                    list(_CLOSED_OBSERVATION_STATUSES)
                                ),
                            ),
                        ),
                    ),
                )
            ).all()
        )
        return len({pid for pid in (disease_parcels | obs_parcels) if pid is not None})

    def _empty(
        self,
        season_year: int,
        period_from: date,
        period_to: date,
        notes: list[str],
    ) -> EnterpriseMonitoringCenter:
        unavailable = EnterpriseMetricAvailability(
            available=False, value=None, note="Nema dodeljenih parcela ili filter ne daje rezultat."
        )
        zero = EnterpriseMetricAvailability(available=True, value=0)
        return EnterpriseMonitoringCenter(
            season_year=season_year,
            period_from=period_from,
            period_to=period_to,
            kpis=EnterpriseMonitoringKpis(
                open_problems=zero if not notes else unavailable,
                new_observations=zero if not notes else unavailable,
                pending_plan_tasks=zero if not notes else unavailable,
                parcels_for_review=zero if not notes else unavailable,
                incomplete_data=zero if not notes else unavailable,
                stale_data=zero if not notes else unavailable,
            ),
            attention_items=[],
            observations=[],
            activities=[],
            plan_items=[],
            weather_signals=[],
            data_quality=[],
            weather=EnterpriseMetricAvailability(
                available=False,
                value=None,
                note="Vremenski indikatori nisu dostupni bez dodeljenih parcela.",
            ),
            filters=EnterpriseMonitoringFiltersMeta(
                suppliers=[],
                parcels=[],
                categories=list(_CATEGORY_LABELS.keys()),
                review_statuses=[s.value for s in ObservationStatus],
                severities=[s.value for s in DiseaseSeverity],
            ),
            notes=notes,
            category_labels=_CATEGORY_LABELS,
        )

    def _score(self, parcel: Parcel, missing: list[str]) -> float:
        required = ["area_hectares", "variety", "planting_year", "trees"]
        present = len(required) - len([f for f in missing if f in required])
        return round(100.0 * present / len(required), 1)

    def _load_plan_items(
        self, parcel_ids: set[UUID], season_year: int
    ) -> list[tuple[PlanningPlanItem, UUID]]:
        seasons = list(
            self.db.scalars(
                select(PlanningSeason).where(
                    PlanningSeason.parcel_id.in_(parcel_ids),
                    PlanningSeason.year == season_year,
                )
            ).all()
        )
        if not seasons:
            return []
        season_by_id = {s.id: s for s in seasons}
        plans = list(
            self.db.scalars(
                select(PlanningPlan).where(
                    PlanningPlan.planning_season_id.in_(list(season_by_id.keys()))
                )
            ).all()
        )
        if not plans:
            return []
        plan_to_season = {p.id: p.planning_season_id for p in plans}
        items = list(
            self.db.scalars(
                select(PlanningPlanItem).where(
                    PlanningPlanItem.plan_id.in_([p.id for p in plans])
                )
            ).all()
        )
        result: list[tuple[PlanningPlanItem, UUID]] = []
        for item in items:
            season_id = plan_to_season.get(item.plan_id)
            season = season_by_id.get(season_id) if season_id else None
            if season is None:
                continue
            result.append((item, season.parcel_id))
        return result

    def _latest_soil_lab_by_parcel(
        self, parcel_ids: set[UUID]
    ) -> dict[UUID, date]:
        rows = self.db.execute(
            select(SoilLabAnalysis.parcel_id, func.max(SoilLabAnalysis.sampled_on)).where(
                SoilLabAnalysis.parcel_id.in_(parcel_ids)
            ).group_by(SoilLabAnalysis.parcel_id)
        ).all()
        return {row[0]: row[1] for row in rows}

    def _weather_signals(
        self,
        *,
        parcel_meta: dict[UUID, tuple[Parcel, Farm | None, str | None]],
        selected_ids: set[UUID],
        category: str | None,
        today: date,
    ) -> tuple[list[EnterpriseWeatherSignal], EnterpriseMetricAvailability]:
        caches = list(
            self.db.scalars(
                select(WeatherForecastCache).where(
                    WeatherForecastCache.parcel_id.in_(selected_ids)
                )
            ).all()
        )
        if not caches:
            return [], EnterpriseMetricAvailability(
                available=False,
                value=None,
                note=(
                    "Nema keširane vremenske prognoze za dodeljene parcele. "
                    "Prognoza se učitava kada proizvođač otvori vremenski pregled parcele (Yr)."
                ),
            )

        signals: list[EnterpriseWeatherSignal] = []
        tz = ZoneInfo(DEFAULT_TIMEZONE)
        now = datetime.now(tz)

        for cache in caches:
            meta = parcel_meta.get(cache.parcel_id)
            if meta is None:
                continue
            parcel, farm, display = meta
            stale = cache.forecast_date != today
            normalized = (
                cache.normalized_response
                if isinstance(cache.normalized_response, dict)
                else {}
            )
            forecast = normalized.get("forecast") or []
            if not isinstance(forecast, list):
                forecast = []

            if stale or not forecast:
                if category in (None, "", "weather_forecast"):
                    signals.append(
                        EnterpriseWeatherSignal(
                            parcel_id=parcel.id,
                            farm_id=parcel.farm_id,
                            parcel_name=parcel.name,
                            farm_name=farm.name if farm else "—",
                            producer_display_name=display,
                            signal_kind="cache_stale" if stale else "cache_empty",
                            title="Prognoza nedostupna ili zastarela",
                            detail=(
                                f"Keš datum: {cache.forecast_date.isoformat()}, "
                                f"fetched_at: {cache.fetched_at.isoformat() if cache.fetched_at else '—'}."
                            ),
                            period_start=cache.forecast_date,
                            period_end=cache.forecast_date,
                            source="Yr (keš)",
                            observed_value=None,
                            threshold=None,
                            reason="Enterprise čita samo postojeći keš; ne pokreće novo preuzimanje.",
                            is_forecast=True,
                            has_matching_observation=False,
                        )
                    )
                continue

            window_end = today + timedelta(days=WEATHER_SIGNAL_DAYS)
            frost_days: list[str] = []
            heat_days: list[str] = []
            for day in forecast:
                if not isinstance(day, dict) or not day.get("date"):
                    continue
                try:
                    day_date = date.fromisoformat(str(day["date"]))
                except ValueError:
                    continue
                if day_date < today or day_date > window_end:
                    continue
                min_t = day.get("min_temperature")
                max_t = day.get("max_temperature")
                if isinstance(min_t, (int, float)) and min_t < FROST_DAY_C:
                    frost_days.append(f"{day_date.isoformat()} ({min_t}°C)")
                if isinstance(max_t, (int, float)) and max_t >= HEAT_SIGNAL_C:
                    heat_days.append(f"{day_date.isoformat()} ({max_t}°C)")

            if frost_days and category in (None, "", "weather_forecast"):
                signals.append(
                    EnterpriseWeatherSignal(
                        parcel_id=parcel.id,
                        farm_id=parcel.farm_id,
                        parcel_name=parcel.name,
                        farm_name=farm.name if farm else "—",
                        producer_display_name=display,
                        signal_kind="forecast_frost",
                        title="Prognoza: moguć mraz",
                        detail="; ".join(frost_days[:5]),
                        period_start=today,
                        period_end=window_end,
                        source="Yr (keš prognoze)",
                        observed_value=frost_days[0],
                        threshold=f"min_temperature < {FROST_DAY_C}°C",
                        reason=(
                            "Signal iz keširane prognoze, ne potvrđena šteta na zasadu. "
                            "Proveriti da li postoji proizvođačko zapažanje weather_damage."
                        ),
                        is_forecast=True,
                        has_matching_observation=False,
                    )
                )
            if heat_days and category in (None, "", "weather_forecast"):
                signals.append(
                    EnterpriseWeatherSignal(
                        parcel_id=parcel.id,
                        farm_id=parcel.farm_id,
                        parcel_name=parcel.name,
                        farm_name=farm.name if farm else "—",
                        producer_display_name=display,
                        signal_kind="forecast_heat",
                        title="Prognoza: visoka temperatura",
                        detail="; ".join(heat_days[:5]),
                        period_start=today,
                        period_end=window_end,
                        source="Yr (keš prognoze)",
                        observed_value=heat_days[0],
                        threshold=f"max_temperature ≥ {HEAT_SIGNAL_C}°C",
                        reason=(
                            "Signal iz keširane prognoze. Nije pretpostavka o šteti niti preporuka tretmana."
                        ),
                        is_forecast=True,
                        has_matching_observation=False,
                    )
                )

        # Annotate matching producer weather_damage observations
        if signals:
            weather_obs_parcels = set(
                self.db.scalars(
                    select(Activity.parcel_id).where(
                        Activity.parcel_id.in_(selected_ids),
                        Activity.observation_category == ObservationCategory.WEATHER_DAMAGE,
                    )
                ).all()
            )
            for signal in signals:
                signal.has_matching_observation = signal.parcel_id in weather_obs_parcels

        age_note = f"Keš učitan u {now.isoformat()}"
        return signals, EnterpriseMetricAvailability(
            available=True,
            value=len(signals),
            note=age_note,
        )

    def _observation_category_key(self, act: Activity) -> str:
        if act.follow_up_of_id:
            return "follow_up"
        if act.semantic_type == ActivitySemanticType.PROBLEM:
            return "reported_problem"
        cat = act.observation_category
        if cat is None:
            return "other_observation"
        if cat.value in ("disease", "pest"):
            return "suspected_disease_pest"
        if cat.value == "weather_damage":
            return "weather_damage"
        if cat.value in ("water_stress", "soil", "nutrient"):
            return "irrigation_soil"
        if act.observation_status == ObservationStatus.NEW:
            return "awaiting_review"
        return "other_observation"

    def _observation_reason(self, act: Activity) -> str:
        bits = []
        if act.observation_severity in (DiseaseSeverity.CRITICAL, DiseaseSeverity.HIGH):
            bits.append(f"Evidentirana težina: {act.observation_severity.value}.")
        if act.observation_status == ObservationStatus.CONFIRMED:
            bits.append("Status: potvrđen, nije označen kao rešen.")
        elif act.observation_status == ObservationStatus.NEW:
            bits.append("Status: novo — čeka pregled.")
        elif act.observation_status == ObservationStatus.MONITORING:
            bits.append("Status: u praćenju.")
        if act.semantic_type == ActivitySemanticType.PROBLEM:
            bits.append("Evidentirano kao problem u dnevniku.")
        if not bits:
            bits.append("Otvoreno zapažanje / problem u izabranom periodu.")
        bits.append("AI hipoteza (ako postoji na drugom mestu) nije potvrđena dijagnoza.")
        return " ".join(bits)

    def _attention_from_observation(
        self, item: EnterpriseMonitoringObservationItem, *, reason: str
    ) -> EnterpriseAttentionItem:
        sev = None
        if item.observation_severity:
            try:
                sev = DiseaseSeverity(item.observation_severity)
            except ValueError:
                sev = None
        awaiting = item.observation_status == ObservationStatus.NEW.value
        confirmed = item.observation_status == ObservationStatus.CONFIRMED.value
        return EnterpriseAttentionItem(
            id=f"activity:{item.id}",
            category=item.category,
            category_label=_CATEGORY_LABELS.get(item.category, item.category),
            parcel_id=item.parcel_id,
            farm_id=item.farm_id,
            parcel_name=item.parcel_name,
            farm_name=item.farm_name,
            producer_display_name=item.producer_display_name,
            event_date=item.performed_on,
            title=item.title,
            description=item.description,
            source=item.source,
            review_status=item.observation_status,
            severity=item.observation_severity,
            reason=reason,
            source_type="activity",
            source_id=item.id,
            priority_rank=self._priority_rank(
                severity=sev,
                awaiting_review=awaiting,
                confirmed_unresolved=confirmed,
                overdue=False,
                data_gap=False,
            ),
        )

    def _priority_rank(
        self,
        *,
        severity: DiseaseSeverity | None,
        awaiting_review: bool,
        confirmed_unresolved: bool,
        overdue: bool,
        data_gap: bool,
    ) -> int:
        if severity in (DiseaseSeverity.CRITICAL, DiseaseSeverity.HIGH):
            return _SEVERITY_RANK.get(severity, 1)
        if confirmed_unresolved:
            return 10
        if awaiting_review:
            return 20
        if overdue:
            return 30
        if data_gap:
            return 50
        return 40

    def _match_filters(
        self,
        *,
        category: str | None,
        review_status: str | None,
        severity: str | None,
        item_category: str,
        item_status: str | None,
        item_severity: str | None,
    ) -> bool:
        if category and item_category != category:
            return False
        if review_status and (item_status or "") != review_status:
            return False
        if severity and (item_severity or "") != severity:
            return False
        return True

    def _filter_options(
        self, parcel_meta: dict[UUID, tuple[Parcel, Farm | None, str | None]]
    ) -> EnterpriseMonitoringFiltersMeta:
        suppliers: dict[UUID, dict[str, Any]] = {}
        parcels: list[dict[str, Any]] = []
        for parcel, farm, display in parcel_meta.values():
            suppliers[parcel.farm_id] = {
                "farm_id": str(parcel.farm_id),
                "label": display or (farm.name if farm else "—"),
                "farm_name": farm.name if farm else "—",
            }
            parcels.append(
                {
                    "parcel_id": str(parcel.id),
                    "farm_id": str(parcel.farm_id),
                    "label": parcel.name,
                }
            )
        return EnterpriseMonitoringFiltersMeta(
            suppliers=list(suppliers.values()),
            parcels=parcels,
            categories=list(_CATEGORY_LABELS.keys()),
            review_statuses=[s.value for s in ObservationStatus],
            severities=[s.value for s in DiseaseSeverity],
        )
