from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.maps import coordinates_as_decimal, resolve_maps_location
from app.models.enums import DiseaseCaseStatus, HealthStatus
from app.models.user import User
from app.repositories.cost import CostRepository
from app.repositories.farm import FarmRepository
from app.schemas.cost import NamedAmount
from app.schemas.dashboard import (
    DashboardParcelRead,
    DashboardRead,
    DashboardStats,
    MonthAmount,
    YearAmount,
)
from app.schemas.farm import FarmRead
from app.schemas.parcel import ParcelRead
from app.services.activity import ActivityService
from app.services.disease import DiseaseService
from app.services.orchard import OrchardService


def _health_count(health: dict, status: HealthStatus) -> int:
    return int(health.get(status, 0) or health.get(status.value, 0) or 0)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.costs = CostRepository(db)
        self.orchard = OrchardService(db)
        self.activities = ActivityService(db)
        self.diseases = DiseaseService(db)

    def get_overview(self, user: User) -> DashboardRead:
        today = date.today()
        year_start = date(today.year, 1, 1)
        year_end = date(today.year, 12, monthrange(today.year, 12)[1])
        month_start = date(today.year, today.month, 1)

        farms = self.farms.list_by_owner(user.id)
        farm = farms[0] if farms else None
        parcels = self.orchard.list_parcels(user.id)
        self._backfill_coordinates(parcels)
        parcels = self.orchard.list_parcels(user.id)

        cases = self.diseases.list_cases(user.id)
        open_cases = [item for item in cases if item.status != DiseaseCaseStatus.RESOLVED]
        open_by_parcel: dict[UUID, int] = {}
        for item in open_cases:
            open_by_parcel[item.parcel_id] = open_by_parcel.get(item.parcel_id, 0) + 1

        dashboard_parcels: list[DashboardParcelRead] = []
        for parcel in parcels:
            health = self.orchard.trees.health_counts(parcel.id)
            dashboard_parcels.append(
                DashboardParcelRead.model_validate(parcel).model_copy(
                    update={
                        "issue_trees": _health_count(health, HealthStatus.ISSUE),
                        "monitoring_trees": _health_count(health, HealthStatus.MONITORING),
                        "healthy_trees": _health_count(health, HealthStatus.HEALTHY),
                        "open_cases": open_by_parcel.get(parcel.id, 0),
                    }
                )
            )

        monthly = self.costs.monthly_totals(user.id, year=today.year)
        year_by_month = [
            MonthAmount(month=month, amount=monthly.get(month, Decimal("0")))
            for month in range(1, 13)
        ]
        year_by_category = [
            NamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
            for item, amount in self.costs.totals_by_category(
                user.id, date_from=year_start, date_to=year_end
            )
        ]
        yearly = self.costs.yearly_totals(user.id)
        planting_years = [parcel.default_planting_year for parcel in parcels if parcel.default_planting_year]
        start_year = min(planting_years) if planting_years else (min(yearly) if yearly else today.year)
        lifetime_by_year = [
            YearAmount(year=year, amount=yearly.get(year, Decimal("0")))
            for year in range(start_year, today.year + 1)
        ]

        stats = DashboardStats(
            parcel_count=len(dashboard_parcels),
            active_tree_count=self.orchard.trees.active_count(user.id),
            area_hectares=self.orchard.parcels.total_area_hectares(user.id),
            year=today.year,
            year_costs=self.costs.sum_for_owner(user.id, date_from=year_start, date_to=year_end),
            month_costs=self.costs.sum_for_owner(user.id, date_from=month_start, date_to=today),
            open_health_cases=len(open_cases),
        )

        return DashboardRead(
            farm=FarmRead.model_validate(farm) if farm is not None else None,
            user_name=user.full_name,
            stats=stats,
            parcels=dashboard_parcels,
            year_by_category=year_by_category,
            year_by_month=year_by_month,
            lifetime_by_year=lifetime_by_year,
            recent_activities=self.activities.list_activities(user.id, limit=6),
            open_cases=open_cases[:6],
            as_of=today,
        )

    def _backfill_coordinates(self, parcels: list[ParcelRead]) -> None:
        changed = False
        for parcel_read in parcels:
            if parcel_read.maps_url and (parcel_read.latitude is None or parcel_read.longitude is None):
                parcel = self.orchard.parcels.get_by_id(parcel_read.id)
                if parcel is None:
                    continue
                try:
                    location = resolve_maps_location(parcel.maps_url, fallback_query=parcel.name)
                except Exception:
                    continue
                if location is None:
                    continue
                parcel.latitude, parcel.longitude = coordinates_as_decimal(location)
                changed = True
        if changed:
            self.db.commit()
