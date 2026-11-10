"""Nutrition Plan Engine (Phase 6).

Uses verified lab analysis as primary soil source; SoilGrids only as secondary context.
No fertilizer product doses in this phase.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity import Activity
from app.models.enums import (
    ActivitySemanticType,
    PlanningExpertReviewStatus,
    PlanningItemKind,
    PlanningItemSource,
    PlanningItemStatus,
    PlanningPlanType,
    PlanningPriorityLevel,
    PlanningScopeType,
    PlanningStream,
    ProductionMethod,
)
from app.models.harvest import HarvestEvent
from app.models.parcel import Parcel
from app.models.planning import PlanningPlan, PlanningSeason
from app.models.soil import SoilProfileSnapshot
from app.repositories.parcel import ParcelRepository
from app.repositories.planning import PlanningPlanItemRepository, PlanningPlanRepository, PlanningSeasonRepository
from app.repositories.soil_lab import SoilLabAnalysisRepository
from app.services.plan_draft import (
    INSUFFICIENT,
    DraftPlanItem,
    clear_generated_items,
    ensure_plan,
    knowledge_citations,
    persist_drafts,
)
from app.services.planting_resolution import resolve_planting_year

logger = logging.getLogger(__name__)


class NutritionPlanEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.seasons = PlanningSeasonRepository(db)
        self.plans = PlanningPlanRepository(db)
        self.items = PlanningPlanItemRepository(db)
        self.parcels = ParcelRepository(db)
        self.soil_lab = SoilLabAnalysisRepository(db)

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

        plan = ensure_plan(season=season, plan_type=PlanningPlanType.NUTRITION, plans=self.plans, db=self.db)
        drafts = self._build_drafts(season, parcel, owner_id, include_knowledge=include_knowledge)

        if replace_generated:
            clear_generated_items(plan, self.db)

        persist_drafts(plan=plan, drafts=drafts, items=self.items, db=self.db)
        self.db.commit()
        self.db.expire_all()
        loaded = self.plans.get_for_owner(plan.id, owner_id)
        assert loaded is not None
        return loaded

    def _build_drafts(
        self,
        season: PlanningSeason,
        parcel: Parcel,
        owner_id: UUID,
        *,
        include_knowledge: bool,
    ) -> list[DraftPlanItem]:
        year = season.year
        today = date.today()
        drafts: list[DraftPlanItem] = []
        missing: list[str] = []

        variety = (parcel.default_variety or "").strip() or None
        planting_year = resolve_planting_year(parcel=parcel) or parcel.default_planting_year
        age = (year - planting_year) if planting_year else None
        organic = parcel.production_method == ProductionMethod.ORGANIC

        if not variety:
            missing.append("sorta / kultivar")
        if planting_year is None:
            missing.append("godina sadnje / starost zasada")

        verified = self.soil_lab.get_latest_verified(parcel.id)
        all_labs = self.soil_lab.list_for_parcel(parcel.id)
        soilgrids = self.db.scalar(
            select(SoilProfileSnapshot).where(SoilProfileSnapshot.parcel_id == parcel.id).limit(1)
        )

        # --- Soil source priority ---
        if verified is not None:
            result_bits = []
            for result in (verified.results or [])[:8]:
                unit = f" {result.unit}" if result.unit else ""
                result_bits.append(f"{result.parameter_code}={result.value}{unit}")
            lab_summary = ", ".join(result_bits) if result_bits else "bez strukturiranih parametara"
            drafts.append(
                DraftPlanItem(
                    title="Pregled potvrđene laboratorijske analize",
                    description=(
                        f"Primarni izvor: VERIFIKOVANA laboratorijska analiza "
                        f"({verified.sampled_on.isoformat()}, {verified.original_filename}). "
                        f"Parametri: {lab_summary}.\n\n"
                        "Ovo NIJE SoilGrids model. Predlog za stručnu proveru pre intervencije."
                    ),
                    reason="Latest verified laboratory analysis je primarni soil source za plan ishrane.",
                    item_kind=PlanningItemKind.SOIL_REVIEW,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.HIGH,
                    priority_reason="Verified lab analysis je najpouzdaniji soil input — zahteva stručni pregled.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    planned_date_from=today,
                    planned_date_to=today + timedelta(days=30),
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                    evidence=[
                        {
                            "source_kind": "laboratory",
                            "analysis_id": str(verified.id),
                            "sampled_on": verified.sampled_on.isoformat(),
                            "verification_status": verified.verification_status.value,
                            "result_count": len(verified.results or []),
                        }
                    ],
                )
            )
            # Older unverified / older verified labs are historical context only.
            older = [row for row in all_labs if row.id != verified.id][:5]
            for old in older:
                drafts.append(
                    DraftPlanItem(
                        title=f"Istorijska lab analiza ({old.sampled_on.isoformat()})",
                        description=(
                            f"HISTORIJSKI KONTEKST — starija analiza ({old.original_filename}, "
                            f"status={old.verification_status.value}). "
                            "Ne zamenjuje latest verified analizu i nije trenutna činjenica."
                        ),
                        reason="Starija lab analiza kao historical context.",
                        item_kind=PlanningItemKind.SOIL_REVIEW,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.HISTORY,
                        status=PlanningItemStatus.MONITOR,
                        priority_level=PlanningPriorityLevel.INFO,
                        priority_reason="Stariji lab zapis — informativno, ne primarni izvor.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        evidence=[
                            {
                                "source_kind": "laboratory_historical",
                                "analysis_id": str(old.id),
                                "sampled_on": old.sampled_on.isoformat(),
                                "verification_status": old.verification_status.value,
                            }
                        ],
                    )
                )
        else:
            missing.append("verified laboratorijska analiza")
            if soilgrids is not None:
                drafts.append(
                    DraftPlanItem(
                        title="SoilGrids kao sekundarni context (nije lab analiza)",
                        description=(
                            "Nema VERIFIKOVANE laboratorijske analize. "
                            "Dostupan je keširani SoilGrids profil kao modelovana procena — "
                            "NIJE laboratorijska analiza i ne sme se tako predstavljati.\n\n"
                            f"{INSUFFICIENT}"
                        ),
                        reason="SoilGrids fallback — samo context, ne lab merenje.",
                        item_kind=PlanningItemKind.SOIL_REVIEW,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.SYSTEM,
                        status=PlanningItemStatus.NEEDS_REVIEW,
                        priority_level=PlanningPriorityLevel.MEDIUM,
                        priority_reason="Bez verified lab-a plan ne može pouzdano predložiti prihranu.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        missing_data=["verified laboratorijska analiza"],
                        evidence=[
                            {
                                "source_kind": "soilgrids",
                                "note": "Modeled estimate — not laboratory measurement",
                                "snapshot_id": str(soilgrids.id),
                            }
                        ],
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )
            else:
                drafts.append(
                    DraftPlanItem(
                        title=INSUFFICIENT,
                        description=(
                            "Nema verified laboratorijske analize ni SoilGrids profila. "
                            f"Nedostaje: {', '.join(sorted(set(missing)))}."
                        ),
                        reason="Nedovoljno soil podataka za pouzdanu procenu ishrane.",
                        item_kind=PlanningItemKind.ASSESSMENT,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.SYSTEM,
                        status=PlanningItemStatus.NEEDS_REVIEW,
                        priority_level=PlanningPriorityLevel.INFO,
                        priority_reason="Bez soil izvora — bez recommendation.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        missing_data=sorted(set(missing)),
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )

        # --- Baseline nutrition monitoring ---
        organic_note = ""
        if organic:
            organic_note = (
                " Organski status: dozvoljeni su samo odgovarajući inputi za organsku proizvodnju. "
                "Konkretni proizvodi se NE preporučuju u ovoj fazi."
            )
        drafts.append(
            DraftPlanItem(
                title="Monitoring ishrane zasada",
                description=(
                    f"Parcela {parcel.name}. Sorta: {variety or 'nepoznata'}. "
                    f"Starost: {age if age is not None else 'nepoznata'} god. "
                    f"Proizvodnja: {'organska' if organic else 'konvencionalna'}."
                    f"{organic_note}\n\n"
                    "Ovo nije predlog doze đubriva."
                ),
                reason="Preventivni nutrition monitoring bez product recommendation.",
                item_kind=PlanningItemKind.NUTRITION_MONITORING,
                stream=PlanningStream.PREVENTIVE,
                source=PlanningItemSource.AGRONOMIC_RULE,
                status=PlanningItemStatus.MONITOR,
                priority_level=PlanningPriorityLevel.LOW,
                priority_reason="Osnovni monitoring ishrane.",
                scope_type=PlanningScopeType.PARCEL,
                scope_id=parcel.id,
                planned_date_from=date(year, 3, 1),
                planned_date_to=date(year, 10, 31),
                missing_data=list(missing),
            )
        )

        if verified is not None:
            drafts.append(
                DraftPlanItem(
                    title="Prozor za procenu prihrane",
                    description=(
                        "Na osnovu verified lab analize predlaže se prozor za stručnu procenu "
                        "da li je prihrana potrebna. Nema konkretnih doza proizvoda u ovoj fazi.\n\n"
                        "Predlog za stručnu proveru."
                    ),
                    reason="Verified soil lab omogućava fertilization window — bez product doses.",
                    item_kind=PlanningItemKind.FERTILIZATION_WINDOW,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.PLANNED,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Postoji verified lab — srednji prioritet za stručnu procenu prozora.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    planned_date_from=date(year, 3, 15),
                    planned_date_to=date(year, 5, 31),
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
            drafts.append(
                DraftPlanItem(
                    title="Predlog za stručnu proveru (ishrana)",
                    description=(
                        "Agronomski zaključak o prihrani mora pregledati stručno lice. "
                        "Sistem ne preporučuje konkretne proizvode."
                    ),
                    reason="Expert review gate za nutrition plan.",
                    item_kind=PlanningItemKind.EXPERT_REVIEW,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.SYSTEM,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Expert review pre bilo kakve intervencije.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )

        # --- Previous fertilization (historical only) ---
        drafts.extend(self._previous_fertilization_items(parcel, season))

        # --- Nutrient observations (reactive monitoring, not confirmation) ---
        drafts.extend(self._nutrient_observation_items(parcel, season))

        # --- Harvest context ---
        harvests = list(
            self.db.scalars(
                select(HarvestEvent)
                .where(HarvestEvent.parcel_id == parcel.id)
                .order_by(HarvestEvent.harvested_on.desc())
                .limit(3)
            ).all()
        )
        if harvests:
            lines = [
                f"{h.harvested_on.isoformat()}: {h.net_quantity} {h.unit}".strip()
                for h in harvests
            ]
            drafts.append(
                DraftPlanItem(
                    title="Kontekst prinosa (istorija)",
                    description=(
                        "HISTORIJSKI KONTEKST prinosa — ne znači automatski potrebu za prihranom:\n"
                        + "\n".join(lines)
                    ),
                    reason="Previous harvest/yield where relevant — historical context only.",
                    item_kind=PlanningItemKind.NUTRITION_MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.HISTORY,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Yield history je kontekst, ne instrukcija.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                )
            )

        # --- Knowledge citations ---
        if include_knowledge and variety:
            evidence, kb_note = knowledge_citations(
                self.db,
                farm_id=parcel.farm_id,
                question=f"Ishrana {variety} leska prihrana monitoring bez doza proizvoda",
            )
            if evidence:
                drafts.append(
                    DraftPlanItem(
                        title="Agriser kontekst za ishranu",
                        description=(
                            "Citati iz Agriser priručnika kao podrška stručnoj proceni. "
                            "Nema product recommendation.\n\nPredlog za stručnu proveru."
                        ),
                        reason="Agriser knowledge retrieval za nutrition domain.",
                        item_kind=PlanningItemKind.NUTRITION_MONITORING,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.AGRONOMIC_RULE,
                        status=PlanningItemStatus.MONITOR,
                        priority_level=PlanningPriorityLevel.LOW,
                        priority_reason="Knowledge citati bez aktuelne intervencije.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        evidence=evidence,
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )
            elif kb_note:
                drafts.append(
                    DraftPlanItem(
                        title="Nedovoljno Agriser dokaza za ishranu",
                        description=f"{kb_note}\n\n{INSUFFICIENT}",
                        reason="Knowledge retrieval nije vratio pouzdan Agriser dokaz.",
                        item_kind=PlanningItemKind.ASSESSMENT,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.SYSTEM,
                        status=PlanningItemStatus.NEEDS_REVIEW,
                        priority_level=PlanningPriorityLevel.INFO,
                        priority_reason="Nema knowledge podrške — informativno.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        missing_data=["Agriser evidence for nutrition"],
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )

        # Previous nutrition plan items as historical
        drafts.extend(self._previous_plan_items(season, parcel, owner_id))

        return drafts

    def _previous_fertilization_items(self, parcel: Parcel, season: PlanningSeason) -> list[DraftPlanItem]:
        stmt = (
            select(Activity)
            .where(
                Activity.parcel_id == parcel.id,
                Activity.semantic_type == ActivitySemanticType.FERTILIZATION,
            )
            .order_by(Activity.performed_on.desc())
            .limit(5)
        )
        rows = list(self.db.scalars(stmt).all())
        drafts: list[DraftPlanItem] = []
        for activity in rows:
            drafts.append(
                DraftPlanItem(
                    title=f"Istorija prihrane ({activity.performed_on.isoformat()})",
                    description=(
                        f"HISTORIJSKI KONTEKST — primenjeno: {activity.title}. "
                        "Ne pretpostavlja se da je prethodna doza ispravna. "
                        "Koristi se samo kao historical context, ne kao trenutna preporuka."
                    ),
                    reason="Previous fertilization activity as historical context only.",
                    item_kind=PlanningItemKind.NUTRITION_MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.HISTORY,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Istorija prihrane nije dokaz ispravnosti doze.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    related_activity_id=activity.id,
                )
            )
        return drafts

    def _nutrient_observation_items(self, parcel: Parcel, season: PlanningSeason) -> list[DraftPlanItem]:
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
        drafts: list[DraftPlanItem] = []
        for activity in self.db.scalars(stmt).all():
            category = activity.observation_category.value if activity.observation_category else ""
            if category not in {"nutrient", "leaf", "soil", "tree_health"}:
                continue
            drafts.append(
                DraftPlanItem(
                    title="Zapažanje relevantno za ishranu — potrebna procena",
                    description=(
                        f"Aktuelno zapažanje ({activity.performed_on.isoformat()}): {activity.title}. "
                        f"Kategorija: {category}. Sistem NE potvrđuje deficit automatski.\n\n"
                        "Predlog za stručnu proveru."
                    ),
                    reason="Reaktivni nutrition tok iz observation istorije.",
                    item_kind=PlanningItemKind.ASSESSMENT,
                    stream=PlanningStream.REACTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.HIGH,
                    priority_reason="Aktuelno nutrient-related zapažanje — viši prioritet za procenu.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    related_activity_id=activity.id,
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
        return drafts

    def _previous_plan_items(
        self,
        season: PlanningSeason,
        parcel: Parcel,
        owner_id: UUID,
    ) -> list[DraftPlanItem]:
        previous = [item for item in self.seasons.list_for_parcel(owner_id, parcel.id) if item.year < season.year]
        if not previous:
            return []
        prev = previous[0]
        nutrition = next((plan for plan in prev.plans if plan.type == PlanningPlanType.NUTRITION), None)
        if nutrition is None or not nutrition.items:
            return []
        return [
            DraftPlanItem(
                title=f"Prethodni plan ishrane ({prev.year})",
                description=(
                    f"HISTORIJSKI KONTEKST — prethodni nutrition plan imao je {len(nutrition.items)} stavki. "
                    "Ne znači da iste mere važe u tekućoj sezoni."
                ),
                reason="Previous nutrition plan as PREVIOUS_PLAN / HISTORY context.",
                item_kind=PlanningItemKind.NUTRITION_MONITORING,
                stream=PlanningStream.PREVENTIVE,
                source=PlanningItemSource.PREVIOUS_PLAN,
                status=PlanningItemStatus.MONITOR,
                priority_level=PlanningPriorityLevel.INFO,
                priority_reason="Prethodni plan je kontekst, ne trenutna činjenica.",
                scope_type=PlanningScopeType.PARCEL,
                scope_id=parcel.id,
                source_season_id=prev.id,
                source_plan_id=nutrition.id,
            )
        ]
