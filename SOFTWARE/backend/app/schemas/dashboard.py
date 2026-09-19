from datetime import date
from decimal import Decimal

from app.schemas.activity import ActivityRead
from app.schemas.common import ORMModel
from app.schemas.cost import NamedAmount
from app.schemas.disease import DiseaseCaseRead
from app.schemas.farm import FarmRead
from app.schemas.parcel import ParcelRead


class MonthAmount(ORMModel):
    month: int
    amount: Decimal


class YearAmount(ORMModel):
    year: int
    amount: Decimal


class DashboardStats(ORMModel):
    parcel_count: int
    active_tree_count: int
    area_hectares: Decimal
    year: int
    year_costs: Decimal
    month_costs: Decimal
    open_health_cases: int
    currency: str = "EUR"


class DashboardParcelRead(ParcelRead):
    issue_trees: int = 0
    monitoring_trees: int = 0
    healthy_trees: int = 0
    open_cases: int = 0


class DashboardRead(ORMModel):
    farm: FarmRead | None
    user_name: str
    stats: DashboardStats
    parcels: list[DashboardParcelRead]
    year_by_category: list[NamedAmount]
    year_by_month: list[MonthAmount]
    lifetime_by_year: list[YearAmount] = []
    recent_activities: list[ActivityRead]
    open_cases: list[DiseaseCaseRead]
    as_of: date
