"""Context request objects used by the engine (internal, not API)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.context.types import ContextRequestType
from app.models.activity import Activity
from app.models.disease import DiseaseCase
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.photo import Photo
from app.models.row import Row
from app.models.tree import Tree


@dataclass(frozen=True)
class ContextRequest:
    request_type: ContextRequestType
    parcel_id: UUID | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None
    photo_id: UUID | None = None
    activity_id: UUID | None = None
    disease_case_id: UUID | None = None
    season_year: int | None = None
    event_date: date | None = None
    query: str | None = None
    include_debug: bool = False


@dataclass
class ResolvedSubject:
    type: str
    farm: Farm
    parcel: Parcel | None
    row: Row | None
    tree: Tree | None
    photo: Photo | None
    activity: Activity | None
    disease_case: DiseaseCase | None
    event_date: date
    event_at: datetime | None
    season_year: int
