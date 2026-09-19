from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import ToolSpec
from app.models.enums import DiseaseCaseStatus, HealthStatus
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.services.activity import ActivityService
from app.services.disease import DiseaseService
from app.services.journal import JournalService
from app.services.knowledge import KnowledgeService
from app.services.orchard import OrchardService


TOOL_SPECS = [
    ToolSpec(
        name="get_parcel_summary",
        description="Pregled parcele: broj stabala, zdravlje, razmaci. Koristite parcel_name ako je poznat.",
        parameters={
            "type": "object",
            "properties": {
                "parcel_name": {"type": "string"},
            },
        },
    ),
    ToolSpec(
        name="get_tree_history",
        description="Dnevnik jednog stabla: zdravlje, otvoreni slučajevi, nedavne aktivnosti. Identifikujte stablo preko public_id npr. R14-T0987.",
        parameters={
            "type": "object",
            "properties": {
                "tree_public_id": {"type": "string"},
                "tree_id": {"type": "string"},
            },
        },
    ),
    ToolSpec(
        name="get_recent_disease_cases",
        description="Nedavna opažanja zdravlja. Filtrirajte po statusu npr. open ili monitoring.",
        parameters={
            "type": "object",
            "properties": {
                "parcel_name": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    ),
    ToolSpec(
        name="get_recent_activities",
        description="Aktivnosti voćnjaka kao što su prskanje, navodnjavanje ili đubrenje. Može da filtrira po broju reda ili nagoveštaju tipa npr. prskanje.",
        parameters={
            "type": "object",
            "properties": {
                "parcel_name": {"type": "string"},
                "row_number": {"type": "integer"},
                "activity_hint": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    ),
    ToolSpec(
        name="get_cost_summary",
        description="Izračunati zbirovi troškova za gazdinstvo ili imenovanu parcelu.",
        parameters={
            "type": "object",
            "properties": {
                "parcel_name": {"type": "string"},
            },
        },
    ),
]


class FarmContextService:
    """Structured retrieval for the agronomist. Never dump the whole database."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)
        self.orchard = OrchardService(db)
        self.activities = ActivityService(db)
        self.diseases = DiseaseService(db)
        self.journal = JournalService(db)
        self.knowledge = KnowledgeService(db)

    def farm_for(self, owner_id: UUID) -> Farm:
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            return None  # type: ignore[return-value]
        return farms[0]

    def dispatch(self, owner_id: UUID, name: str, arguments: dict) -> dict:
        handlers = {
            "get_parcel_summary": self.get_parcel_summary,
            "get_tree_history": self.get_tree_history,
            "get_recent_disease_cases": self.get_recent_disease_cases,
            "get_recent_activities": self.get_recent_activities,
            "get_cost_summary": self.get_cost_summary,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Nepoznat alat {name}"}
        return handler(owner_id, **_clean_args(arguments))

    def get_parcel_summary(self, owner_id: UUID, parcel_name: str | None = None, **_: object) -> dict:
        parcel = self._parcel(owner_id, parcel_name)
        if parcel is None:
            return {"error": "Parcela nije pronađena"}
        twin = self.orchard.get_twin(parcel.id, owner_id)
        stats = twin.stats
        return {
            "id": str(parcel.id),
            "name": parcel.name,
            "area_hectares": str(parcel.area_hectares) if parcel.area_hectares is not None else None,
            "row_count": stats.row_count,
            "tree_count": stats.total_trees,
            "healthy_trees": stats.healthy_trees,
            "monitoring_trees": stats.monitoring_trees,
            "issue_trees": stats.issue_trees,
            "unknown_trees": stats.unknown_trees,
            "row_spacing_m": str(parcel.row_spacing_m) if parcel.row_spacing_m is not None else None,
            "tree_spacing_m": str(parcel.tree_spacing_m) if parcel.tree_spacing_m is not None else None,
            "maps_url": parcel.maps_url,
        }

    def get_tree_history(
        self,
        owner_id: UUID,
        tree_public_id: str | None = None,
        tree_id: str | None = None,
        **_: object,
    ) -> dict:
        tree = self._tree(owner_id, tree_public_id=tree_public_id, tree_id=tree_id)
        if tree is None:
            return {"error": "Stablo nije pronađeno"}
        journal = self.journal.get_tree_journal(tree.parcel_id, tree.id, owner_id)
        return {
            "id": str(tree.id),
            "public_id": tree.public_id,
            "row_number": journal.tree.row_number,
            "position_in_row": journal.tree.position_in_row,
            "variety": tree.variety,
            "health_status": tree.health_status.value if isinstance(tree.health_status, HealthStatus) else tree.health_status,
            "open_case_count": len(journal.open_cases),
            "open_cases": [
                {"id": str(item.id), "title": item.title, "status": item.status.value, "severity": item.severity.value}
                for item in journal.open_cases[:5]
            ],
            "recent_activities": [
                {"id": str(item.id), "title": item.title, "performed_on": str(item.performed_on)}
                for item in journal.activities[:5]
            ],
            "direct_cost_total": str(journal.direct_cost_total),
        }

    def get_recent_disease_cases(
        self,
        owner_id: UUID,
        parcel_name: str | None = None,
        status: str | None = None,
        limit: int = 8,
        **_: object,
    ) -> dict:
        parcel = self._parcel(owner_id, parcel_name)
        parsed_status = None
        if status:
            try:
                parsed_status = DiseaseCaseStatus(status)
            except ValueError:
                parsed_status = None
        cases = self.diseases.list_cases(
            owner_id,
            parcel_id=parcel.id if parcel else None,
            status=parsed_status,
        )
        if parsed_status is None:
            cases = [item for item in cases if item.status != DiseaseCaseStatus.RESOLVED]
        rows = []
        for item in cases[: max(1, min(int(limit), 20))]:
            rows.append(
                {
                    "id": str(item.id),
                    "title": item.title,
                    "status": item.status.value,
                    "severity": item.severity.value,
                    "category": item.category.value,
                    "detected_on": str(item.detected_on),
                    "parcel_name": item.parcel_name,
                    "tree_public_id": item.tree_public_id,
                }
            )
        return {"cases": rows}

    def get_recent_activities(
        self,
        owner_id: UUID,
        parcel_name: str | None = None,
        row_number: int | None = None,
        activity_hint: str | None = None,
        limit: int = 10,
        **_: object,
    ) -> dict:
        parcel = self._parcel(owner_id, parcel_name)
        row_id = None
        if parcel is not None and row_number is not None:
            row = self.db.scalars(
                select(Row).where(Row.parcel_id == parcel.id, Row.row_number == int(row_number))
            ).first()
            row_id = row.id if row else None
        records = self.activities.list_activities(
            owner_id,
            parcel_id=parcel.id if parcel else None,
            row_id=row_id,
        )
        hint = (activity_hint or "").lower()
        if hint:
            records = [
                item
                for item in records
                if hint in item.title.lower()
                or hint in item.activity_type.name.lower()
                or hint in item.activity_type.slug.lower()
            ]
        # When asking about a row, also include parcel-level work that covered that row.
        if row_number is not None and parcel is not None:
            extra = [
                item
                for item in self.activities.list_activities(owner_id, parcel_id=parcel.id)
                if item.row_id is None
                and (not hint or hint in item.title.lower() or hint in item.activity_type.slug.lower())
            ]
            merged = {item.id: item for item in extra + records}
            records = sorted(merged.values(), key=lambda item: item.performed_on, reverse=True)
        rows = []
        for item in records[: max(1, min(int(limit), 20))]:
            rows.append(
                {
                    "id": str(item.id),
                    "title": item.title,
                    "activity_type": item.activity_type.name,
                    "performed_on": str(item.performed_on),
                    "scope_type": item.scope_type.value,
                    "parcel_name": item.parcel_name,
                    "row_number": item.row_number,
                    "tree_public_id": item.tree_public_id,
                    "total_cost": str(item.total_cost),
                }
            )
        return {"activities": rows}

    def get_cost_summary(self, owner_id: UUID, parcel_name: str | None = None, **_: object) -> dict:
        parcel = self._parcel(owner_id, parcel_name) if parcel_name else None
        summary = self.activities.cost_summary(owner_id, parcel.id if parcel else None)
        return {
            "currency": summary.currency,
            "total_costs": str(summary.total_costs),
            "current_year_costs": str(summary.current_year_costs),
            "current_month_costs": str(summary.current_month_costs),
            "cost_per_tree": str(summary.cost_per_tree) if summary.cost_per_tree is not None else None,
            "parcel_name": parcel.name if parcel else None,
            "by_category": [{"name": item.name, "amount": str(item.amount)} for item in summary.by_category],
        }

    def tree_context_for_analysis(self, owner_id: UUID, tree_id: UUID | None, parcel_id: UUID) -> str:
        if tree_id is None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            return f"Parcela {parcel.name if parcel else parcel_id}. Nije izabrano pojedinačno stablo."
        tree = self.db.get(Tree, tree_id)
        if tree is None:
            return "Zapis o stablu nedostaje."
        history = self.get_tree_history(owner_id, tree_id=str(tree.id))
        return json.dumps(history, ensure_ascii=False)

    def _parcel(self, owner_id: UUID, parcel_name: str | None) -> Parcel | None:
        parcels = self.parcels.list_for_owner(owner_id)
        if not parcels:
            return None
        if not parcel_name:
            preferred = next(
                (
                    item
                    for item in parcels
                    if "north" in item.name.lower() or "sever" in item.name.lower()
                ),
                None,
            )
            return preferred or parcels[0]
        needle = parcel_name.lower()
        for item in parcels:
            if needle in item.name.lower() or needle == item.code.lower():
                return item
        return parcels[0]

    def _tree(
        self,
        owner_id: UUID,
        *,
        tree_public_id: str | None = None,
        tree_id: str | None = None,
    ) -> Tree | None:
        stmt = (
            select(Tree)
            .join(Parcel, Tree.parcel_id == Parcel.id)
            .join(Farm, Parcel.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )
        if tree_id:
            stmt = stmt.where(Tree.id == UUID(str(tree_id)))
        elif tree_public_id:
            stmt = stmt.where(Tree.public_id == tree_public_id.upper())
        else:
            return None
        return self.db.scalars(stmt).first()


def _clean_args(arguments: dict) -> dict:
    cleaned = {}
    for key, value in arguments.items():
        if value in ("", None):
            continue
        cleaned[key] = value
    return cleaned
