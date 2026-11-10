"""Protection Plan Engine (Phase 5 foundation).

Two separate streams:
  A) PREVENTIVE / MONITORING — calendar-style checks, historical risk as HISTORICAL only
  B) REACTIVE — based on current observations; never auto-confirms disease

No pesticide product recommendations in this phase.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context.engine import ContextEngine
from app.context.request import ContextRequest
from app.context.types import ContextRequestType
from app.core.exceptions import NotFoundError
from app.knowledge.retrieve import retrieve_evidence
from app.models.activity import Activity
from app.models.enums import (
    ActivitySemanticType,
    PlanningExpertReviewStatus,
    PlanningItemKind,
    PlanningItemSource,
    PlanningItemStatus,
    PlanningPlanStatus,
    PlanningPlanType,
    PlanningPriorityLevel,
    PlanningScopeType,
    PlanningStream,
    ProductionMethod,
)
from app.models.parcel import Parcel
from app.models.planning import PlanningPlan, PlanningPlanItem, PlanningSeason
from app.models.row import Row
from app.repositories.parcel import ParcelRepository
from app.repositories.planning import PlanningPlanItemRepository, PlanningPlanRepository, PlanningSeasonRepository
from app.services.planting_resolution import resolve_planting_year

logger = logging.getLogger(__name__)

PRIORITY_SCORE = {
    PlanningPriorityLevel.HIGH: 90,
    PlanningPriorityLevel.MEDIUM: 50,
    PlanningPriorityLevel.LOW: 25,
    PlanningPriorityLevel.INFO: 10,
}

AGRISER_FALLBACK = (
    "Na osnovu dostupnih Agriser priručnika ne mogu pouzdano da utvrdim odgovor. "
    "Preporučujem proveru sa stručnim agronomom."
)

INSUFFICIENT = "Nedovoljno podataka za pouzdanu procenu."


@dataclass
class DraftProtectionItem:
    title: str
    description: str
    reason: str
    item_kind: PlanningItemKind
    stream: PlanningStream
    source: PlanningItemSource
    status: PlanningItemStatus
    priority_level: PlanningPriorityLevel
    priority_reason: str
    scope_type: PlanningScopeType
    scope_id: UUID
    planned_date_from: date | None = None
    planned_date_to: date | None = None
    expert_review_status: PlanningExpertReviewStatus = PlanningExpertReviewStatus.NOT_REQUIRED
    evidence: list[dict] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    related_activity_id: UUID | None = None
    source_season_id: UUID | None = None
    source_plan_id: UUID | None = None
    source_plan_item_id: UUID | None = None


class ProtectionPlanEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.seasons = PlanningSeasonRepository(db)
        self.plans = PlanningPlanRepository(db)
        self.items = PlanningPlanItemRepository(db)
        self.parcels = ParcelRepository(db)

    def generate(
        self,
        season_id: UUID,
        owner_id: UUID,
        *,
        replace_generated: bool = True,
        include_knowledge: bool = True,
    ) -> PlanningPlan:
        season = self.seasons.get_for_owner(season_id, owner_id)
        if season is None:
            raise NotFoundError("Sezona planiranja nije pronađena")
        parcel = self.parcels.get_for_owner(season.parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")

        plan = self._ensure_protection_plan(season)
        drafts = self._build_drafts(season, parcel, owner_id, include_knowledge=include_knowledge)

        if replace_generated:
            self._clear_generated_items(plan)

        for draft in drafts:
            self.items.add(
                PlanningPlanItem(
                    plan_id=plan.id,
                    scope_type=draft.scope_type,
                    scope_id=draft.scope_id,
                    title=draft.title[:255],
                    description=draft.description,
                    planned_date_from=draft.planned_date_from,
                    planned_date_to=draft.planned_date_to,
                    priority=PRIORITY_SCORE[draft.priority_level],
                    priority_level=draft.priority_level,
                    priority_reason=draft.priority_reason,
                    item_kind=draft.item_kind,
                    stream=draft.stream,
                    reason=draft.reason,
                    evidence=draft.evidence,
                    missing_data=draft.missing_data,
                    related_activity_id=draft.related_activity_id,
                    status=draft.status,
                    source=draft.source,
                    expert_review_status=draft.expert_review_status,
                    source_season_id=draft.source_season_id,
                    source_plan_id=draft.source_plan_id,
                    source_plan_item_id=draft.source_plan_item_id,
                )
            )

        if plan.status == PlanningPlanStatus.DRAFT and drafts:
            plan.status = PlanningPlanStatus.READY_FOR_REVIEW
        self.db.commit()
        self.db.expire_all()
        loaded = self.plans.get_for_owner(plan.id, owner_id)
        assert loaded is not None
        return loaded

    def _ensure_protection_plan(self, season: PlanningSeason) -> PlanningPlan:
        for plan in season.plans:
            if plan.type == PlanningPlanType.PROTECTION:
                return plan
        plan = PlanningPlan(
            planning_season_id=season.id,
            type=PlanningPlanType.PROTECTION,
            status=PlanningPlanStatus.DRAFT,
            version=1,
        )
        self.plans.add(plan)
        self.db.flush()
        return plan

    def _clear_generated_items(self, plan: PlanningPlan) -> None:
        removable = {
            PlanningItemSource.SYSTEM,
            PlanningItemSource.AGRONOMIC_RULE,
            PlanningItemSource.HISTORY,
        }
        for item in list(plan.items):
            if item.source in removable and item.status in {
                PlanningItemStatus.PLANNED,
                PlanningItemStatus.MONITOR,
                PlanningItemStatus.NEEDS_REVIEW,
            }:
                self.db.delete(item)
        self.db.flush()

    def _build_drafts(
        self,
        season: PlanningSeason,
        parcel: Parcel,
        owner_id: UUID,
        *,
        include_knowledge: bool,
    ) -> list[DraftProtectionItem]:
        year = season.year
        today = date.today()
        drafts: list[DraftProtectionItem] = []
        missing: list[str] = []

        variety = (parcel.default_variety or "").strip() or None
        planting_year = resolve_planting_year(parcel=parcel) or parcel.default_planting_year
        age = (year - planting_year) if planting_year else None
        organic = parcel.production_method == ProductionMethod.ORGANIC if parcel.production_method else False

        if not variety:
            missing.append("sorta / kultivar")
        if planting_year is None:
            missing.append("godina sadnje / starost zasada")

        # --- A) PREVENTIVE ---
        drafts.append(
            self._preventive_baseline(
                parcel=parcel,
                year=year,
                variety=variety,
                age=age,
                organic=organic,
                missing=list(missing),
            )
        )

        drafts.extend(self._historical_risk_items(season, parcel, owner_id))

        # Weather-aware monitoring (preventive, not treatment).
        weather_note, weather_missing = self._weather_hint(parcel, owner_id)
        if weather_missing:
            missing.extend(weather_missing)
        if weather_note:
            drafts.append(
                DraftProtectionItem(
                    title="Monitoring usled vremenskih uslova",
                    description=(
                        f"{weather_note}\n\n"
                        "Predlog za stručnu proveru — ovo nije instrukcija za tretman."
                    ),
                    reason="Aktuelna vremenska prognoza ukazuje na uslove koji zaslužuju pojačan pregled.",
                    item_kind=PlanningItemKind.MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Vremenski uslovi mogu povećati rizik; prioritet srednji jer nema potvrđenog problema.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    planned_date_from=today,
                    planned_date_to=today + timedelta(days=7),
                    expert_review_status=PlanningExpertReviewStatus.NOT_REQUIRED,
                )
            )

        # Knowledge enrichment for preventive calendar (citations only).
        if include_knowledge and variety:
            evidence, kb_note = self._knowledge_citations(
                farm_id=parcel.farm_id,
                question=f"Kalendar zaštite {variety} monitoring preventivni pregledi",
            )
            if evidence:
                drafts.append(
                    DraftProtectionItem(
                        title="Preventivni monitoring prema Agriser priručniku",
                        description=(
                            "Pregledati zasad prema dostupnim Agriser uputstvima za period sezone. "
                            "Ne predlaže se konkretan pesticid u ovoj fazi.\n\n"
                            "Predlog za stručnu proveru."
                        ),
                        reason="Agriser knowledge retrieval za preventivni kalendar zaštite.",
                        item_kind=PlanningItemKind.MONITORING,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.AGRONOMIC_RULE,
                        status=PlanningItemStatus.MONITOR,
                        priority_level=PlanningPriorityLevel.LOW,
                        priority_reason="Preventivni monitoring bez aktuelnog zapažanja — nizak prioritet.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        planned_date_from=date(year, 3, 1),
                        planned_date_to=date(year, 10, 31),
                        evidence=evidence,
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )
            elif kb_note:
                drafts.append(
                    DraftProtectionItem(
                        title="Nedovoljno Agriser dokaza za preventivni kalendar",
                        description=f"{kb_note}\n\n{INSUFFICIENT}",
                        reason="Knowledge retrieval nije vratio pouzdan Agriser dokaz.",
                        item_kind=PlanningItemKind.ASSESSMENT,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.SYSTEM,
                        status=PlanningItemStatus.NEEDS_REVIEW,
                        priority_level=PlanningPriorityLevel.INFO,
                        priority_reason="Nema pouzdane knowledge podrške — samo informativno.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        missing_data=["Agriser evidence for protection calendar"],
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )

        # --- B) REACTIVE (current-year observations only) ---
        drafts.extend(self._reactive_observation_items(season, parcel, owner_id, include_knowledge=include_knowledge))

        # Insufficient baseline data → explicit non-recommendation.
        if len(missing) >= 2 and not any(d.stream == PlanningStream.REACTIVE for d in drafts):
            drafts.append(
                DraftProtectionItem(
                    title=INSUFFICIENT,
                    description=(
                        "Plan zaštite ne može pouzdano da predloži intervenišuće korake. "
                        f"Nedostaje: {', '.join(sorted(set(missing)))}."
                    ),
                    reason="Nedovoljno osnovnih podataka parcele za pouzdanu procenu.",
                    item_kind=PlanningItemKind.ASSESSMENT,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.SYSTEM,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Nedostaju ključni podaci — bez preporuke.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    missing_data=sorted(set(missing)),
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )

        return drafts

    def _preventive_baseline(
        self,
        *,
        parcel: Parcel,
        year: int,
        variety: str | None,
        age: int | None,
        organic: bool,
        missing: list[str],
    ) -> DraftProtectionItem:
        parts = [
            f"Parcela: {parcel.name}.",
            f"Sorta: {variety or 'nepoznata'}.",
            f"Starost zasada: {age if age is not None else 'nepoznata'} god.",
            f"Proizvodnja: {'organska' if organic else 'konvencionalna'}.",
        ]
        if missing:
            parts.append(f"Nedostaje: {', '.join(missing)}.")
        organic_note = (
            " Organski status zahteva poseban oprez pri izboru mera (bez pesticidne preporuke u ovoj fazi)."
            if organic
            else ""
        )
        return DraftProtectionItem(
            title="Preventivni monitoring zasada",
            description=(
                "Pregledati zasad zbog potencijalnih rizika tokom sezone. "
                "Ovo nije predlog hemijskog tretmana."
                f"{organic_note}\n\n" + " ".join(parts)
            ),
            reason="Preventivni tok plana zaštite — monitoring bez potvrđenog problema.",
            item_kind=PlanningItemKind.MONITORING,
            stream=PlanningStream.PREVENTIVE,
            source=PlanningItemSource.AGRONOMIC_RULE,
            status=PlanningItemStatus.MONITOR,
            priority_level=PlanningPriorityLevel.LOW,
            priority_reason="Osnovni preventivni monitoring cele parcele.",
            scope_type=PlanningScopeType.PARCEL,
            scope_id=parcel.id,
            planned_date_from=date(year, 3, 1),
            planned_date_to=date(year, 10, 31),
            missing_data=missing,
            expert_review_status=PlanningExpertReviewStatus.NOT_REQUIRED,
        )

    def _historical_risk_items(
        self,
        season: PlanningSeason,
        parcel: Parcel,
        owner_id: UUID,
    ) -> list[DraftProtectionItem]:
        """Previous-year observations become HISTORICAL RISK / MONITORING — not current facts."""
        previous = [
            item
            for item in self.seasons.list_for_parcel(owner_id, parcel.id)
            if item.year < season.year
        ]
        if not previous:
            return []
        prev = previous[0]
        start = date(prev.year, 1, 1)
        end = date(prev.year, 12, 31)
        stmt = (
            select(Activity)
            .where(
                Activity.parcel_id == parcel.id,
                Activity.performed_on >= start,
                Activity.performed_on <= end,
                Activity.semantic_type.in_(
                    [
                        ActivitySemanticType.OBSERVATION,
                        ActivitySemanticType.PROBLEM,
                        ActivitySemanticType.MONITORING,
                    ]
                ),
            )
            .order_by(Activity.performed_on.desc())
            .limit(5)
        )
        rows = list(self.db.scalars(stmt).all())
        drafts: list[DraftProtectionItem] = []
        for activity in rows:
            scope_type, scope_id = self._scope_from_activity(activity, parcel.id)
            category = activity.observation_category.value if activity.observation_category else "unknown"
            drafts.append(
                DraftProtectionItem(
                    title=f"Istorijski rizik / monitoring ({prev.year})",
                    description=(
                        f"HISTORIJSKI KONTEKST — nije potvrđeno da problem postoji u {season.year}. "
                        f"U {prev.year}. zabeleženo: {activity.title}. "
                        f"Kategorija tada: {category}. "
                        "Predlaže se preventivni monitoring, ne tretman.\n\n"
                        "Predlog za stručnu proveru."
                    ),
                    reason=(
                        f"Prethodna sezona ({prev.year}) imala je zapažanje/problem — "
                        "mapirano kao historical risk, ne kao trenutna činjenica."
                    ),
                    item_kind=PlanningItemKind.MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.HISTORY,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.LOW,
                    priority_reason="Istorijski rizik bez aktuelne potvrde — nizak prioritet.",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    planned_date_from=date(season.year, 3, 1),
                    planned_date_to=date(season.year, 6, 30),
                    related_activity_id=activity.id,
                    source_season_id=prev.id,
                    expert_review_status=PlanningExpertReviewStatus.NOT_REQUIRED,
                )
            )
        return drafts

    def _reactive_observation_items(
        self,
        season: PlanningSeason,
        parcel: Parcel,
        owner_id: UUID,
        *,
        include_knowledge: bool,
    ) -> list[DraftProtectionItem]:
        start = date(season.year, 1, 1)
        end = date(season.year, 12, 31)
        stmt = (
            select(Activity)
            .where(
                Activity.parcel_id == parcel.id,
                Activity.performed_on >= start,
                Activity.performed_on <= end,
                Activity.semantic_type.in_(
                    [ActivitySemanticType.OBSERVATION, ActivitySemanticType.PROBLEM]
                ),
            )
            .order_by(Activity.performed_on.desc())
            .limit(10)
        )
        observations = list(self.db.scalars(stmt).all())
        drafts: list[DraftProtectionItem] = []
        for activity in observations:
            scope_type, scope_id = self._scope_from_activity(activity, parcel.id)
            category = activity.observation_category.value if activity.observation_category else "unknown"
            evidence: list[dict] = []
            kb_suffix = ""
            if include_knowledge:
                evidence, kb_note = self._knowledge_citations(
                    farm_id=parcel.farm_id,
                    question=f"Zapažanje {category} leska procena bez potvrde bolesti",
                )
                if not evidence and kb_note:
                    kb_suffix = f"\n\n{kb_note}"
            where = self._scope_label(scope_type, scope_id)
            drafts.append(
                DraftProtectionItem(
                    title="Potrebna dodatna procena problema",
                    description=(
                        f"Na {where} postoji novo zapažanje ({activity.performed_on.isoformat()}): "
                        f"{activity.title}. Kategorija: {category}. "
                        "Sistem NE potvrđuje bolest/štetočinu automatski.\n\n"
                        "Predlog za stručnu proveru."
                        f"{kb_suffix}"
                    ),
                    reason="Reaktivni tok: aktuelno zapažanje zahteva procenu, ne automatski tretman.",
                    item_kind=PlanningItemKind.ASSESSMENT,
                    stream=PlanningStream.REACTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.HIGH
                    if category in {"disease", "pest"}
                    else PlanningPriorityLevel.MEDIUM,
                    priority_reason=(
                        "Aktuelno zapažanje na poznatom scope-u — viši prioritet za procenu; "
                        "bez automatskog zaključka o bolesti."
                    ),
                    scope_type=scope_type,
                    scope_id=scope_id,
                    planned_date_from=activity.performed_on,
                    planned_date_to=activity.performed_on + timedelta(days=14),
                    related_activity_id=activity.id,
                    evidence=evidence,
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
            drafts.append(
                DraftProtectionItem(
                    title="Predlog za stručnu proveru",
                    description=(
                        f"Zapažanje na {where} treba da pregleda stručno lice pre bilo kakve intervencije. "
                        "Nema pesticide recommendation u ovoj fazi."
                    ),
                    reason="Agronomski zaključak / potencijalna intervencija zahteva expert review.",
                    item_kind=PlanningItemKind.EXPERT_REVIEW,
                    stream=PlanningStream.REACTIVE,
                    source=PlanningItemSource.SYSTEM,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Expert review gate pre intervencije.",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    related_activity_id=activity.id,
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
        return drafts

    def _weather_hint(self, parcel: Parcel, owner_id: UUID) -> tuple[str | None, list[str]]:
        try:
            request = ContextRequest(
                request_type=ContextRequestType.SEASON_ANALYSIS,
                parcel_id=parcel.id,
                include_debug=False,
            )
            context = ContextEngine(self.db).build_context(owner_id, request)
        except Exception:
            logger.exception("Context weather hint failed")
            return None, ["vremenska prognoza"]
        weather = getattr(context, "weather", None)
        if not weather:
            return None, ["vremenska prognoza"]
        summary = getattr(weather, "summary", None) or getattr(weather, "note", None)
        if isinstance(summary, str) and summary.strip():
            return summary.strip()[:400], []
        return "Dostupna je vremenska prognoza — proveriti uslove pre obilaska.", []

    def _knowledge_citations(self, *, farm_id: UUID, question: str) -> tuple[list[dict], str | None]:
        try:
            package = retrieve_evidence(self.db, farm_id, question, agriser_only=True)
        except Exception:
            logger.exception("Knowledge retrieval failed for protection plan")
            return [], AGRISER_FALLBACK
        if not package.sources or not package.sufficient_evidence:
            return [], AGRISER_FALLBACK
        citations: list[dict] = []
        for source in package.sources[:5]:
            citations.append(
                {
                    "document_id": str(source.document_id) if source.document_id else None,
                    "document_title": source.document_title,
                    "pages": list(source.pages or []),
                    "section": source.section,
                    "chunk_id": str(source.chunk_id) if source.chunk_id else None,
                    "score": source.score,
                }
            )
        return citations, None

    def _scope_from_activity(self, activity: Activity, parcel_id: UUID) -> tuple[PlanningScopeType, UUID]:
        if activity.tree_id:
            return PlanningScopeType.TREE, activity.tree_id
        if activity.row_id:
            return PlanningScopeType.ROW, activity.row_id
        return PlanningScopeType.PARCEL, parcel_id

    def _scope_label(self, scope_type: PlanningScopeType, scope_id: UUID) -> str:
        if scope_type == PlanningScopeType.PARCEL:
            parcel = self.db.get(Parcel, scope_id)
            return f"parceli {parcel.name if parcel else scope_id}"
        if scope_type == PlanningScopeType.ROW:
            row = self.db.get(Row, scope_id)
            return f"redu {row.row_number if row else scope_id}"
        return f"stablu {scope_id}"
