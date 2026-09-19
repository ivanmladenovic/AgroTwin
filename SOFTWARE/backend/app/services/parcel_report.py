from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, exists, extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity import Activity, ActivityType
from app.models.disease import DiseaseCase, DiseaseObservation
from app.models.enums import ActivityStatus, DiseaseCaseStatus, HealthStatus, ScopeType, TreeStatus
from app.models.harvest import HarvestEvent
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.cost import CostRepository
from app.repositories.harvest import HarvestRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.tree import TreeRepository
from app.schemas.report import (
    NamedCount,
    OptionalAmount,
    ParcelAnnualReportRead,
    ReportActivitiesSummary,
    ReportAttentionTree,
    ReportComparisonRow,
    ReportFinancialSummary,
    ReportHarvestQuality,
    ReportHealthSummary,
    ReportKpi,
    ReportMonthAmount,
    ReportNamedAmount,
    ReportParcelSummary,
    ReportPlannedActivity,
    ReportProblemRow,
    ReportProblemSummary,
    ReportQualityAverage,
    ReportQualityCategory,
    ReportTimelineItem,
    ReportTrend,
    ReportYieldSummary,
    YearChange,
)
from app.services.harvest_calc import (
    HarvestMeasure,
    first_last_dates,
    parcel_scope_only,
    quality_from_measures,
    total_kg,
)
from app.services.parcel_report_calc import (
    build_executive_summary,
    change_direction,
    change_tone,
    percent_change,
    pick_monthly_highlights,
    ratio,
    year_bounds,
    yield_kg_from_line_items,
)

ATTENTION_LIMIT = 8
PLANNED_LIMIT = 7
TOP_ACTIVITY_COSTS = 5
OPEN_CASE_STATUSES = (DiseaseCaseStatus.OPEN, DiseaseCaseStatus.MONITORING)
KPI_LABELS = {
    "total_trees": "Ukupno stabala",
    "healthy_trees": "Zdrava stabla",
    "attention_trees": "Zahtevaju pažnju",
    "activities_completed": "Urađene aktivnosti",
    "activities_planned": "Planirane aktivnosti",
    "annual_cost": "Godišnji trošak",
    "yield_kg": "Prinos",
    "cost_per_hectare": "Trošak po hektaru",
}
COMPARISON_LABELS = {
    "attention_trees": "Stabla koja zahtevaju pažnju",
    "activities_completed": "Urađene aktivnosti",
    "annual_cost": "Ukupni troškovi",
    "yield_kg": "Prinos",
    "problem_cases": "Slučajevi problema",
}


class ParcelReportService:
    """Yearly orchard report. Section methods are isolated so later AI/weather/drone inputs can be added."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.parcels = ParcelRepository(db)
        self.trees = TreeRepository(db)
        self.costs = CostRepository(db)
        self.harvests = HarvestRepository(db)

    def get_parcel_annual_report(self, owner_id: UUID, parcel_id: UUID, year: int) -> ParcelAnnualReportRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")

        start, end = year_bounds(year)
        previous_year = year - 1
        prev_start, prev_end = year_bounds(previous_year)
        today = date.today()
        generated_at = datetime.now()

        health = self._health_summary(parcel.id)
        attention = self._attention_trees(parcel.id, today)
        current_activities = self._activities_summary(parcel.id, start, end)
        previous_activities = self._activities_summary(parcel.id, prev_start, prev_end)
        planned = self._planned_activities(parcel.id, year, today)
        previous_year_has_records = self._year_has_records(owner_id, parcel.id, prev_start, prev_end)
        financial = self._financial_summary(
            owner_id,
            parcel.id,
            start,
            end,
            prev_start,
            prev_end,
            previous_year_has_records=previous_year_has_records,
        )
        problems = self._problem_summary(parcel.id, start, end)
        previous_problems = self._problem_summary(parcel.id, prev_start, prev_end)
        current_yield = self._yield_summary(parcel.id, start, end, parcel.area_hectares, health.active_trees)
        previous_yield = self._yield_summary(parcel.id, prev_start, prev_end, parcel.area_hectares, health.active_trees)
        financial.cost_per_kg = self._optional(
            ratio(financial.annual_cost.value, current_yield.total_kg) if financial.annual_cost.available else None
        )

        comparison_available = previous_year_has_records
        comparison = self._comparison(
            current_activities=current_activities,
            previous_activities=previous_activities,
            financial=financial,
            problems=problems,
            previous_problems=previous_problems,
            current_yield=current_yield,
            previous_yield=previous_yield,
            comparison_available=comparison_available,
        )
        kpis = self._kpis(
            health=health,
            activities=current_activities,
            previous_activities=previous_activities,
            financial=financial,
            current_yield=current_yield,
            previous_yield=previous_yield,
            comparison_available=comparison_available,
        )
        top_row = problems.by_row[0].row_number if problems.recorded and problems.by_row else None
        summary = build_executive_summary(
            year=year,
            previous_year=previous_year,
            parcel_name=parcel.name,
            activities_completed=current_activities.completed_count,
            annual_cost=financial.annual_cost.value,
            costs_available=financial.annual_cost.available,
            yield_kg=current_yield.total_kg if current_yield.recorded else None,
            yield_change_percent=(
                comparison_row_percent(comparison, "yield_kg") if current_yield.recorded and previous_yield.recorded else None
            ),
            attention_count=health.attention_count,
            top_problem_row=top_row,
        )
        return ParcelAnnualReportRead(
            parcel_summary=ReportParcelSummary(
                parcel_id=parcel.id,
                parcel_name=parcel.name,
                parcel_code=parcel.code,
                farm_name=parcel.farm.name if parcel.farm else "",
                year=year,
                previous_year=previous_year,
                generated_at=generated_at,
                generated_on=today,
                area_hectares=parcel.area_hectares,
                available_years=self._available_years(owner_id, parcel.id, parcel.default_planting_year, today.year),
                comparison_available=comparison_available,
            ),
            executive_summary=summary,
            kpis=kpis,
            health_summary=health,
            trees_requiring_attention=attention,
            trees_requiring_control=attention,
            activities_summary=current_activities,
            planned_activities=planned,
            financial_summary=financial,
            problem_summary=problems,
            yield_summary=current_yield,
            previous_year_comparison=comparison,
            yearly_trend=ReportTrend(kind="monthly_costs", months=financial.monthly),
        )

    def _health_summary(self, parcel_id: UUID) -> ReportHealthSummary:
        health = self.trees.health_counts(parcel_id)
        status = self.trees.status_counts(parcel_id)
        total = sum(status.values())
        active = status.get(TreeStatus.ACTIVE, 0)
        issue = health.get(HealthStatus.ISSUE, 0)
        monitoring = health.get(HealthStatus.MONITORING, 0)
        return ReportHealthSummary(
            total_trees=total,
            active_trees=active,
            healthy=health.get(HealthStatus.HEALTHY, 0),
            monitoring=monitoring,
            issue=issue,
            unknown=health.get(HealthStatus.UNKNOWN, 0),
            removed=status.get(TreeStatus.REMOVED, 0),
            replaced=status.get(TreeStatus.REPLACED, 0),
            attention_count=issue + monitoring,
        )

    def _attention_trees(self, parcel_id: UUID, today: date) -> list[ReportAttentionTree]:
        open_case = exists(
            select(DiseaseCase.id).where(
                DiseaseCase.tree_id == Tree.id,
                DiseaseCase.status.in_(OPEN_CASE_STATUSES),
            )
        )
        last_observation = (
            select(func.max(DiseaseObservation.observed_on))
            .join(DiseaseCase, DiseaseObservation.disease_case_id == DiseaseCase.id)
            .where(DiseaseCase.tree_id == Tree.id)
            .correlate(Tree)
            .scalar_subquery()
        )
        last_inspection = (
            select(func.max(Activity.performed_on))
            .join(ActivityType, Activity.activity_type_id == ActivityType.id)
            .where(
                Activity.tree_id == Tree.id,
                ActivityType.slug == "inspection",
                Activity.status != ActivityStatus.CANCELLED,
            )
            .correlate(Tree)
            .scalar_subquery()
        )
        priority = case(
            (Tree.health_status == HealthStatus.ISSUE, 0),
            (open_case, 1),
            (Tree.health_status == HealthStatus.MONITORING, 2),
            else_=3,
        )
        stmt = (
            select(
                Tree,
                Row.row_number,
                open_case.label("has_open_case"),
                last_observation.label("last_observation"),
                last_inspection.label("last_inspection"),
            )
            .join(Row, Tree.row_id == Row.id)
            .where(
                Tree.parcel_id == parcel_id,
                Tree.status != TreeStatus.REMOVED,
                or_(
                    Tree.health_status.in_((HealthStatus.ISSUE, HealthStatus.MONITORING)),
                    open_case,
                ),
            )
            .order_by(priority, Tree.public_id)
            .limit(ATTENTION_LIMIT)
        )
        rows = []
        for tree, row_number, has_open_case, last_observation_on, last_inspection_on in self.db.execute(stmt):
            last_check = _latest_date(last_observation_on, last_inspection_on)
            if tree.health_status == HealthStatus.ISSUE:
                reason = "Aktivan problem"
            elif has_open_case:
                reason = "Nerešen slučaj"
            else:
                reason = "Praćenje"
            rows.append(
                ReportAttentionTree(
                    tree_id=tree.id,
                    public_id=tree.public_id,
                    row_id=tree.row_id,
                    row_number=row_number,
                    health_status=tree.health_status.value,
                    reason=reason,
                    last_check_on=last_check,
                    days_since_check=(today - last_check).days if last_check else None,
                )
            )
        return rows

    def _activities_summary(
        self,
        parcel_id: UUID,
        start: date,
        end: date,
    ) -> ReportActivitiesSummary:
        recorded = self._has_activities(parcel_id)
        completed = (
            select(ActivityType.id, ActivityType.name, ActivityType.slug, func.count())
            .join(Activity, Activity.activity_type_id == ActivityType.id)
            .where(
                Activity.parcel_id == parcel_id,
                Activity.performed_on >= start,
                Activity.performed_on <= end,
                Activity.status == ActivityStatus.COMPLETED,
            )
            .group_by(ActivityType.id)
            .order_by(func.count().desc(), ActivityType.sort_order)
        )
        by_type = [
            NamedCount(id=type_id, name=name, slug=slug, count=int(count))
            for type_id, name, slug, count in self.db.execute(completed)
        ]
        completed_count = sum(item.count for item in by_type)
        planned_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(Activity)
                .where(
                    Activity.parcel_id == parcel_id,
                    Activity.performed_on >= start,
                    Activity.performed_on <= end,
                    Activity.status.in_((ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS)),
                )
            )
            or 0
        )
        highlight_rows = self.db.execute(
            select(Activity.performed_on, Activity.title, ActivityType.name, ActivityType.slug)
            .join(ActivityType, Activity.activity_type_id == ActivityType.id)
            .where(
                Activity.parcel_id == parcel_id,
                Activity.performed_on >= start,
                Activity.performed_on <= end,
                Activity.status == ActivityStatus.COMPLETED,
            )
            .order_by(Activity.performed_on.asc())
        ).all()
        highlights = pick_monthly_highlights(
            [
                {
                    "performed_on": performed_on,
                    "title": title,
                    "name": type_name,
                    "slug": slug,
                }
                for performed_on, title, type_name, slug in highlight_rows
            ]
        )
        return ReportActivitiesSummary(
            completed_count=completed_count,
            planned_count=planned_count,
            recorded=recorded or completed_count > 0 or planned_count > 0,
            by_type=by_type,
            timeline=[
                ReportTimelineItem(
                    month=item["performed_on"].month,
                    performed_on=item["performed_on"],
                    title=item["title"],
                    activity_type_name=item["name"],
                    activity_type_slug=item["slug"],
                )
                for item in highlights
            ],
        )

    def _planned_activities(
        self,
        parcel_id: UUID,
        year: int,
        today: date,
    ) -> list[ReportPlannedActivity]:
        start, end = year_bounds(year)
        from_date = max(start, today) if year >= today.year else start
        stmt = (
            select(Activity, ActivityType.name, Row.row_number, Tree.public_id)
            .join(ActivityType, Activity.activity_type_id == ActivityType.id)
            .outerjoin(Row, Activity.row_id == Row.id)
            .outerjoin(Tree, Activity.tree_id == Tree.id)
            .where(
                Activity.parcel_id == parcel_id,
                Activity.performed_on >= from_date,
                Activity.performed_on <= end,
                Activity.status.in_((ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS)),
            )
            .order_by(Activity.performed_on.asc(), Activity.created_at.asc())
            .limit(PLANNED_LIMIT)
        )
        return [
            ReportPlannedActivity(
                id=activity.id,
                performed_on=activity.performed_on,
                title=activity.title,
                activity_type_name=type_name,
                row_number=row_number,
                tree_public_id=tree_public_id,
            )
            for activity, type_name, row_number, tree_public_id in self.db.execute(stmt)
        ]

    def _financial_summary(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        start: date,
        end: date,
        prev_start: date,
        prev_end: date,
        *,
        previous_year_has_records: bool,
    ) -> ReportFinancialSummary:
        ever = self.costs.exists_for_owner(owner_id, parcel_id=parcel_id)
        annual = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_from=start, date_to=end)
        previous = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_from=prev_start, date_to=prev_end)
        historical = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_to=end)
        by_category = [
            ReportNamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
            for item, amount in self.costs.totals_by_category(
                owner_id, parcel_id=parcel_id, date_from=start, date_to=end
            )
        ]
        by_activity = [
            ReportNamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
            for item, amount in self.costs.totals_by_activity_type(
                owner_id, parcel_id=parcel_id, date_from=start, date_to=end
            )[:TOP_ACTIVITY_COSTS]
        ]
        monthly_map = self.costs.monthly_totals(owner_id, year=start.year, parcel_id=parcel_id)
        monthly = [ReportMonthAmount(month=month, amount=monthly_map.get(month, Decimal("0"))) for month in range(1, 13)]
        area = self.parcels.total_area_hectares(owner_id, parcel_id)
        active_trees = self.trees.active_count(owner_id, parcel_id)
        annual_available = ever
        return ReportFinancialSummary(
            recorded=ever,
            annual_cost=self._optional(annual if annual_available else None),
            previous_year_cost=self._optional(previous if ever and previous_year_has_records else None),
            historical_cost=self._optional(historical if ever else None),
            by_category=by_category,
            by_activity=by_activity,
            monthly=monthly,
            cost_per_hectare=self._optional(ratio(annual, area) if annual_available else None),
            cost_per_tree=self._optional(ratio(annual, active_trees) if annual_available else None),
            cost_per_kg=self._optional(None),
        )

    def _problem_summary(self, parcel_id: UUID, start: date, end: date) -> ReportProblemSummary:
        ever = self.db.scalar(select(DiseaseCase.id).where(DiseaseCase.parcel_id == parcel_id).limit(1)) is not None
        status_rows = self.db.execute(
            select(DiseaseCase.status, func.count())
            .where(
                DiseaseCase.parcel_id == parcel_id,
                DiseaseCase.detected_on >= start,
                DiseaseCase.detected_on <= end,
            )
            .group_by(DiseaseCase.status)
        ).all()
        counts = {status: int(count) for status, count in status_rows}
        total = sum(counts.values())
        category_rows = self.db.execute(
            select(DiseaseCase.category, func.count())
            .where(
                DiseaseCase.parcel_id == parcel_id,
                DiseaseCase.detected_on >= start,
                DiseaseCase.detected_on <= end,
            )
            .group_by(DiseaseCase.category)
            .order_by(func.count().desc())
        ).all()
        row_rows = self.db.execute(
            select(Row.id, Row.row_number, func.count())
            .join(DiseaseCase, DiseaseCase.row_id == Row.id)
            .where(
                DiseaseCase.parcel_id == parcel_id,
                DiseaseCase.detected_on >= start,
                DiseaseCase.detected_on <= end,
            )
            .group_by(Row.id)
            .order_by(func.count().desc(), Row.row_number)
        ).all()
        return ReportProblemSummary(
            recorded=ever,
            total=total,
            open_count=counts.get(DiseaseCaseStatus.OPEN, 0),
            monitoring_count=counts.get(DiseaseCaseStatus.MONITORING, 0),
            resolved_count=counts.get(DiseaseCaseStatus.RESOLVED, 0),
            by_category=[
                NamedCount(name=category.value, slug=category.value, count=int(count))
                for category, count in category_rows
            ],
            by_row=[
                ReportProblemRow(row_id=row_id, row_number=row_number, count=int(count))
                for row_id, row_number, count in row_rows
            ],
        )

    def _yield_summary(
        self,
        parcel_id: UUID,
        start: date,
        end: date,
        area_hectares: Decimal | None,
        active_trees: int,
    ) -> ReportYieldSummary:
        empty = ReportYieldSummary(
            recorded=False,
            total_kg=None,
            harvest_events=None,
            first_harvest_date=None,
            last_harvest_date=None,
            per_hectare=self._optional(None),
            per_tree=self._optional(None),
            quality=None,
            source=None,
        )
        harvests = list(
            self.db.scalars(
                select(HarvestEvent).where(
                    HarvestEvent.parcel_id == parcel_id,
                    HarvestEvent.harvested_on >= start,
                    HarvestEvent.harvested_on <= end,
                    HarvestEvent.scope_type == ScopeType.PARCEL,
                )
            ).all()
        )
        if harvests:
            measures = [
                HarvestMeasure(
                    scope_type=item.scope_type.value if hasattr(item.scope_type, "value") else str(item.scope_type),
                    harvested_on=item.harvested_on,
                    gross=item.gross_quantity,
                    loss=item.loss_quantity,
                    unit=item.unit,
                    moisture_percent=item.moisture_percent,
                    damaged_percent=item.damaged_percent,
                    empty_nuts_percent=item.empty_nuts_percent,
                    foreign_material_percent=item.foreign_material_percent,
                    quality_category=item.quality_category,
                )
                for item in harvests
            ]
            net = total_kg(parcel_scope_only(measures), "net")
            first, last = first_last_dates(measures)
            quality_payload = quality_from_measures(measures)
            return ReportYieldSummary(
                recorded=net is not None,
                total_kg=net,
                harvest_events=len(harvests),
                first_harvest_date=first,
                last_harvest_date=last,
                per_hectare=self._optional(ratio(net, area_hectares)),
                per_tree=self._optional(ratio(net, active_trees) if active_trees > 0 else None),
                quality=self._harvest_quality(quality_payload),
                source="harvest_event",
            )

        stmt = (
            select(Activity)
            .join(ActivityType, Activity.activity_type_id == ActivityType.id)
            .where(
                Activity.parcel_id == parcel_id,
                Activity.performed_on >= start,
                Activity.performed_on <= end,
                Activity.status == ActivityStatus.COMPLETED,
                ActivityType.slug == "harvesting",
            )
        )
        activities = list(self.db.scalars(stmt).all())
        total = Decimal("0")
        recorded_events = 0
        first_on: date | None = None
        last_on: date | None = None
        for activity in activities:
            kg = yield_kg_from_line_items(activity.line_items, activity.quantity, activity.unit)
            if kg is None:
                continue
            total += kg
            recorded_events += 1
            first_on = activity.performed_on if first_on is None else min(first_on, activity.performed_on)
            last_on = activity.performed_on if last_on is None else max(last_on, activity.performed_on)
        if recorded_events == 0:
            return empty
        return ReportYieldSummary(
            recorded=True,
            total_kg=total,
            harvest_events=recorded_events,
            first_harvest_date=first_on,
            last_harvest_date=last_on,
            per_hectare=self._optional(ratio(total, area_hectares)),
            per_tree=self._optional(ratio(total, active_trees) if active_trees > 0 else None),
            quality=None,
            source="activity",
        )

    def _harvest_quality(self, payload: dict) -> ReportHarvestQuality | None:
        if not payload.get("recorded"):
            return None

        def average(data: dict) -> ReportQualityAverage:
            return ReportQualityAverage(
                available=bool(data.get("available")),
                value=data.get("value"),
                method=data.get("method"),
                sample_count=int(data.get("sample_count") or 0),
            )

        return ReportHarvestQuality(
            recorded=True,
            moisture=average(payload.get("moisture") or {}),
            damaged=average(payload.get("damaged") or {}),
            empty_nuts=average(payload.get("empty_nuts") or {}),
            foreign_material=average(payload.get("foreign_material") or {}),
            categories=[
                ReportQualityCategory(
                    category=item["category"].value if hasattr(item["category"], "value") else str(item["category"]),
                    net_kg=item["net_kg"],
                    event_count=item["event_count"],
                )
                for item in payload.get("categories") or []
            ],
        )

    def _kpis(
        self,
        *,
        health: ReportHealthSummary,
        activities: ReportActivitiesSummary,
        previous_activities: ReportActivitiesSummary,
        financial: ReportFinancialSummary,
        current_yield: ReportYieldSummary,
        previous_yield: ReportYieldSummary,
        comparison_available: bool,
    ) -> list[ReportKpi]:
        return [
            self._kpi(
                "total_trees",
                "count",
                Decimal(health.active_trees),
                available=True,
                previous=None,
                comparison_available=False,
            ),
            self._kpi(
                "healthy_trees",
                "count",
                Decimal(health.healthy),
                available=True,
                previous=None,
                comparison_available=False,
            ),
            self._kpi(
                "attention_trees",
                "count",
                Decimal(health.attention_count),
                available=True,
                previous=None,
                comparison_available=False,
            ),
            self._kpi(
                "activities_completed",
                "count",
                Decimal(activities.completed_count),
                available=activities.recorded,
                previous=Decimal(previous_activities.completed_count) if comparison_available else None,
                comparison_available=comparison_available,
            ),
            self._kpi(
                "activities_planned",
                "count",
                Decimal(activities.planned_count),
                available=True,
                previous=None,
                comparison_available=False,
            ),
            self._kpi(
                "annual_cost",
                "money",
                financial.annual_cost.value,
                available=financial.annual_cost.available,
                previous=financial.previous_year_cost.value if financial.previous_year_cost.available else None,
                comparison_available=financial.previous_year_cost.available,
            ),
            self._kpi(
                "yield_kg",
                "mass",
                current_yield.total_kg,
                available=current_yield.recorded,
                previous=previous_yield.total_kg if previous_yield.recorded else None,
                comparison_available=current_yield.recorded and previous_yield.recorded,
            ),
            self._kpi(
                "cost_per_hectare",
                "money",
                financial.cost_per_hectare.value,
                available=financial.cost_per_hectare.available,
                previous=None,
                comparison_available=False,
            ),
        ]

    def _kpi(
        self,
        key: str,
        kind: str,
        value: Decimal | None,
        *,
        available: bool,
        previous: Decimal | None,
        comparison_available: bool,
    ) -> ReportKpi:
        return ReportKpi(
            key=key,
            label=KPI_LABELS[key],
            available=available,
            kind=kind,  # type: ignore[arg-type]
            value=value if available else None,
            change=self._change(key, value if available else None, previous if comparison_available else None),
        )

    def _comparison(
        self,
        *,
        current_activities: ReportActivitiesSummary,
        previous_activities: ReportActivitiesSummary,
        financial: ReportFinancialSummary,
        problems: ReportProblemSummary,
        previous_problems: ReportProblemSummary,
        current_yield: ReportYieldSummary,
        previous_yield: ReportYieldSummary,
        comparison_available: bool,
    ) -> list[ReportComparisonRow]:
        if not comparison_available:
            return []
        rows: list[ReportComparisonRow] = []
        if current_activities.recorded or previous_activities.recorded:
            rows.append(
                self._comparison_row(
                    "activities_completed",
                    "count",
                    Decimal(previous_activities.completed_count),
                    Decimal(current_activities.completed_count),
                )
            )
        if financial.annual_cost.available and financial.previous_year_cost.available:
            rows.append(
                self._comparison_row(
                    "annual_cost",
                    "money",
                    financial.previous_year_cost.value,
                    financial.annual_cost.value,
                )
            )
        if current_yield.recorded and previous_yield.recorded:
            rows.append(
                self._comparison_row(
                    "yield_kg",
                    "mass",
                    previous_yield.total_kg,
                    current_yield.total_kg,
                )
            )
        if problems.recorded and previous_problems.recorded:
            rows.append(
                self._comparison_row(
                    "problem_cases",
                    "count",
                    Decimal(previous_problems.total),
                    Decimal(problems.total),
                )
            )
        return rows

    def _comparison_row(
        self,
        key: str,
        kind: str,
        previous: Decimal | None,
        current: Decimal | None,
    ) -> ReportComparisonRow:
        return ReportComparisonRow(
            key=key,
            label=COMPARISON_LABELS[key],
            kind=kind,  # type: ignore[arg-type]
            previous=previous,
            current=current,
            change=self._change(key, current, previous),
        )

    def _change(self, key: str, current: Decimal | None, previous: Decimal | None) -> YearChange:
        direction = change_direction(current, previous)
        percent = percent_change(current, previous)
        available = current is not None and previous is not None
        return YearChange(
            available=available,
            previous=previous if available else None,
            percent=percent,
            direction=direction,
            tone=change_tone(key, direction) if available else None,
        )

    def _available_years(self, owner_id: UUID, parcel_id: UUID, planting_year: int | None, current_year: int) -> list[int]:
        years = {current_year}
        if planting_year:
            years.add(planting_year)
        activity_years = self.db.scalars(
            select(extract("year", Activity.performed_on)).where(Activity.parcel_id == parcel_id).distinct()
        )
        years.update(int(year) for year in activity_years if year is not None)
        years.update(self.costs.yearly_totals(owner_id, parcel_id=parcel_id).keys())
        years.update(self.harvests.years_for_parcel(parcel_id))
        return sorted(year for year in years if 1990 <= year <= 2100)

    def _has_activities(self, parcel_id: UUID) -> bool:
        return self.db.scalar(select(Activity.id).where(Activity.parcel_id == parcel_id).limit(1)) is not None

    def _year_has_records(self, owner_id: UUID, parcel_id: UUID, start: date, end: date) -> bool:
        activity = self.db.scalar(
            select(Activity.id)
            .where(
                Activity.parcel_id == parcel_id,
                Activity.performed_on >= start,
                Activity.performed_on <= end,
            )
            .limit(1)
        )
        if activity is not None:
            return True
        if self.costs.exists_for_owner(owner_id, parcel_id=parcel_id, date_from=start, date_to=end):
            return True
        if self.harvests.exists_in_range(parcel_id, start, end):
            return True
        case = self.db.scalar(
            select(DiseaseCase.id)
            .where(
                DiseaseCase.parcel_id == parcel_id,
                DiseaseCase.detected_on >= start,
                DiseaseCase.detected_on <= end,
            )
            .limit(1)
        )
        return case is not None

    @staticmethod
    def _optional(value: Decimal | None) -> OptionalAmount:
        return OptionalAmount(available=value is not None, value=value)


def comparison_row_percent(rows: list[ReportComparisonRow], key: str) -> Decimal | None:
    for row in rows:
        if row.key == key:
            return row.change.percent
    return None


def _latest_date(*values: date | None) -> date | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None
