from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import ScopeType
from app.schemas.activity import ActivityRead
from app.schemas.cost import CostItemRead
from app.schemas.disease import DiseaseCaseRead, ObservationRead, PhotoRead
from app.schemas.orchard import TreeDetailRead


class TimelineEvent(BaseModel):
    occurred_on: date
    kind: Literal["activity", "disease", "observation"]
    title: str
    subtitle: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    scope_type: ScopeType | None = None
    activity_id: UUID | None = None
    disease_id: UUID | None = None
    observation_id: UUID | None = None
    is_direct: bool = True


class TreeJournalRead(BaseModel):
    tree: TreeDetailRead
    timeline: list[TimelineEvent]
    activities: list[ActivityRead]
    related_activities: list[ActivityRead]
    diseases: list[DiseaseCaseRead]
    open_cases: list[DiseaseCaseRead]
    observations: list[ObservationRead]
    photos: list[PhotoRead]
    costs: list[CostItemRead]
    related_costs: list[CostItemRead]
    direct_cost_total: Decimal
    orchard_cost_total: Decimal
    currency: str = "EUR"


class TreeOptionRead(BaseModel):
    id: UUID
    public_id: str
    row_id: UUID
    row_number: int
    position_in_row: int
    variety: str | None = None
