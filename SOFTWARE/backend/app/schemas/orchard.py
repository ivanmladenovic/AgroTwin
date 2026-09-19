from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import HealthStatus, TreeStatus, WellLocation
from app.schemas.common import IDSchema
from app.schemas.farm import FarmRead
from app.schemas.parcel import ParcelRead


class RowRead(IDSchema):
    parcel_id: UUID
    row_number: int
    tree_count: int
    name: str | None
    variety: str | None = None


class TreeMapRead(IDSchema):
    parcel_id: UUID
    row_id: UUID
    public_id: str
    row_number: int
    position_in_row: int
    planting_year: int | None
    variety: str | None
    status: TreeStatus
    health_status: HealthStatus
    has_severe_case: bool = False
    normalized_x: Decimal
    normalized_y: Decimal


class TreeDetailRead(TreeMapRead):
    activity_count: int
    disease_issue_count: int
    total_cost: Decimal
    journal_path: str


class OrchardStats(BaseModel):
    total_trees: int
    row_count: int
    trees_per_row: int | None
    area_hectares: Decimal | None
    row_spacing_m: Decimal | None
    tree_spacing_m: Decimal | None
    healthy_trees: int
    monitoring_trees: int
    issue_trees: int
    unknown_trees: int
    active_trees: int
    removed_trees: int
    replaced_trees: int


class WellRead(BaseModel):
    location: WellLocation
    x: Decimal
    y: Decimal


class OrchardTwinRead(BaseModel):
    parcel: ParcelRead
    farm: FarmRead
    rows: list[RowRead]
    trees: list[TreeMapRead]
    stats: OrchardStats
    well: WellRead | None
    width_m: Decimal
    height_m: Decimal
