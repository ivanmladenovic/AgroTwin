"""Provider contract for the Context Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from app.context.profiles import ContextProfile
from app.context.request import ContextRequest, ResolvedSubject
from app.context.types import DataQualityStatus, WarningType
from app.models.enums import ScopeType


@dataclass
class ContextWarning:
    type: WarningType
    source: str
    message: str


@dataclass
class RankedItem:
    kind: str
    id: str
    payload: Any
    relevance_score: float
    reasons: list[str]
    scope: str | None = None
    date: Any = None
    temporal_relation: str | None = None


@dataclass
class ProviderResult:
    source: str
    source_type: str
    status: DataQualityStatus
    items: list[RankedItem] = field(default_factory=list)
    payload: Any = None
    warnings: list[ContextWarning] = field(default_factory=list)
    collected: int = 0
    filtered: int = 0

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass
class EngineQuery:
    owner_id: UUID
    request: ContextRequest
    subject: ResolvedSubject
    profile: ContextProfile
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ContextDataProvider(Protocol):
    def get_source_type(self) -> str: ...

    def supports(self, query: EngineQuery) -> bool: ...

    def collect(self, query: EngineQuery) -> ProviderResult: ...


def scope_from_enum(value: ScopeType | str | None) -> str:
    if value is None:
        return "PARCEL"
    raw = value.value if isinstance(value, ScopeType) else str(value)
    return raw.upper()


def scope_id_for(scope: str, *, farm_id=None, parcel_id=None, row_id=None, tree_id=None):
    mapping = {
        "TREE": tree_id,
        "ROW": row_id,
        "PARCEL": parcel_id,
        "FARM": farm_id,
    }
    return mapping.get(scope)
