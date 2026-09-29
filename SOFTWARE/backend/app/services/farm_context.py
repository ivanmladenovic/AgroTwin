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
from app.repositories.soil import SoilProfileRepository
from app.services.activity import ActivityService
from app.services.disease import DiseaseService
from app.services.journal import JournalService
from app.services.knowledge import KnowledgeService
from app.services.orchard import OrchardService
from app.soil.properties import PROVIDER_NAME, SOURCE_TYPE


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
    ToolSpec(
        name="get_soil_lab_analyses",
        description=(
            "Laboratorijske analize zemljišta sa parcele (PDF/fotografije koje je korisnik otpremio). "
            "Vraća spisak i izvučeni tekst. Koristite kad korisnik pita za analizu zemljišta ili mišljenje o lab rezultatu."
        ),
        parameters={
            "type": "object",
            "properties": {
                "parcel_name": {"type": "string"},
                "limit": {"type": "integer"},
                "include_text": {"type": "boolean"},
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
        self.soil = SoilProfileRepository(db)
        self.orchard = OrchardService(db)
        self.activities = ActivityService(db)
        self.diseases = DiseaseService(db)
        self.journal = JournalService(db)
        self.knowledge = KnowledgeService(db)
        from app.services.soil_lab import SoilLabAnalysisService

        self.soil_lab = SoilLabAnalysisService(db)

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
            "get_soil_lab_analyses": self.get_soil_lab_analyses,
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
            "soil": self._soil_context(parcel),
        }

    def format_parcel_brief(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        parcel_name: str | None = None,
        include_soil_lab_text: bool = False,
    ) -> str | None:
        """Cheap one-shot parcel snapshot for advice prompts (no extra Gemini round)."""
        if parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                return None
            summary = self.get_parcel_summary(owner_id, parcel_name=parcel.name)
            resolved_parcel_id = parcel.id
        else:
            summary = self.get_parcel_summary(owner_id, parcel_name=parcel_name)
            if not summary or summary.get("error"):
                return None
            try:
                resolved_parcel_id = UUID(str(summary["id"]))
            except (KeyError, ValueError, TypeError):
                resolved_parcel_id = None
        if not summary or summary.get("error"):
            return None
        soil = summary.get("soil") or {}
        soil_bits: list[str] = []
        if isinstance(soil, dict) and soil.get("available"):
            data = soil.get("data")
            if isinstance(data, dict):
                for key, label in (("ph", "pH"), ("pH", "pH"), ("organic_matter", "humus"), ("humus", "humus")):
                    if key not in data:
                        continue
                    raw = data[key]
                    value = raw
                    if isinstance(raw, dict):
                        first = next(iter(raw.values()), None)
                        if isinstance(first, dict) and first.get("value") is not None:
                            value = first["value"]
                        else:
                            value = first
                    if value is not None and not isinstance(value, dict):
                        soil_bits.append(f"{label} {value}")
                    break
            if soil.get("status"):
                soil_bits.append(f"status {soil['status']}")
        lines = [
            "FARM BRIEF (već učitano — ne zovi get_parcel_summary samo zbog ovoga):",
            (
                f"Parcela {summary.get('name')}: "
                f"{summary.get('area_hectares') or '?'} ha, "
                f"{summary.get('row_count') or '?'} redova, "
                f"{summary.get('tree_count') or '?'} stabala "
                f"(zdrava {summary.get('healthy_trees') or 0}, "
                f"praćenje {summary.get('monitoring_trees') or 0}, "
                f"problem {summary.get('issue_trees') or 0})."
            ),
        ]
        if soil_bits:
            lines.append(
                "Modelirano zemljište (SoilGrids, nije laboratorijski PDF): "
                + ", ".join(str(item) for item in soil_bits[:4])
                + "."
            )
        if resolved_parcel_id is not None:
            lab_block = self.soil_lab.format_context_block(
                resolved_parcel_id,
                owner_id,
                include_text=include_soil_lab_text,
            )
            if lab_block:
                lines.append(lab_block)
        return "\n".join(lines)

    def get_soil_lab_analyses(
        self,
        owner_id: UUID,
        parcel_name: str | None = None,
        limit: int = 3,
        include_text: bool = True,
        **_: object,
    ) -> dict:
        parcel = self._parcel(owner_id, parcel_name)
        if parcel is None:
            return {"error": "Parcela nije pronađena", "analyses": []}
        return self.soil_lab.context_payload(
            parcel.id,
            owner_id,
            limit=limit,
            include_text=include_text,
        )

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

    def _soil_context(self, parcel: Parcel) -> dict:
        snapshot = self.soil.get_for_parcel(parcel.id)
        if snapshot is None:
            return {
                "source": PROVIDER_NAME,
                "source_type": SOURCE_TYPE,
                "available": False,
                "data": None,
            }
        return {
            "source": PROVIDER_NAME,
            "source_type": SOURCE_TYPE,
            "available": True,
            "status": snapshot.status,
            "fetched_at": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None,
            "data": _compact_soil_values(snapshot.values),
        }

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


def _compact_soil_values(values: object) -> object:
    """Keep only a short surface summary for LLM tool results."""
    if not isinstance(values, dict):
        return values
    compact: dict = {}
    for key in ("ph", "cec", "clay", "sand", "silt", "organic_carbon", "total_nitrogen"):
        item = values.get(key)
        if item is None:
            continue
        if isinstance(item, dict):
            # Prefer the shallowest depth band if nested.
            depths = item.get("depths") if isinstance(item.get("depths"), dict) else item
            if isinstance(depths, dict) and depths:
                first_key = next(iter(depths))
                compact[key] = {first_key: depths[first_key]}
            else:
                compact[key] = item
        else:
            compact[key] = item
    return compact or values


def _clean_args(arguments: dict) -> dict:
    cleaned = {}
    for key, value in arguments.items():
        if value in ("", None):
            continue
        cleaned[key] = value
    return cleaned
