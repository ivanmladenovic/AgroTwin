"""Irrigation Plan Engine (Phase 6).

Progressive system profile on parcel; calculations always label assumptions.
No invented parameters when data is missing.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity import Activity
from app.models.enums import (
    ActivitySemanticType,
    IrrigationType,
    PlanningExpertReviewStatus,
    PlanningItemKind,
    PlanningItemSource,
    PlanningItemStatus,
    PlanningPlanType,
    PlanningPriorityLevel,
    PlanningScopeType,
    PlanningStream,
)
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
    season_context,
)
from app.services.planting_resolution import resolve_planting_year

logger = logging.getLogger(__name__)


class IrrigationPlanEngine:
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

        plan = ensure_plan(season=season, plan_type=PlanningPlanType.IRRIGATION, plans=self.plans, db=self.db)
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
        density = None
        if parcel.row_spacing_m and parcel.tree_spacing_m:
            density = f"razmak redova {parcel.row_spacing_m} m × stabla {parcel.tree_spacing_m} m"

        if not parcel.has_irrigation:
            drafts.append(
                DraftPlanItem(
                    title="Parcela nema označen sistem za navodnjavanje",
                    description=(
                        "Korisnik nije označio da parcela ima sistem za navodnjavanje. "
                        "Plan ne izmišlja tehničke parametre. "
                        "Moguć je samo monitoring vlage / vremenskih uslova.\n\n"
                        f"{INSUFFICIENT}"
                    ),
                    reason="has_irrigation=false — bez system calculation.",
                    item_kind=PlanningItemKind.ASSESSMENT,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.SYSTEM,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Bez sistema nema irrigation calculation.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    missing_data=["sistem za navodnjavanje"],
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
            drafts.append(
                DraftPlanItem(
                    title="Monitoring vlage / suše (bez sistema)",
                    description=(
                        f"Parcela {parcel.name}. Sorta: {variety or 'nepoznata'}. "
                        f"Starost: {age if age is not None else 'nepoznata'} god. "
                        "Pregledati znakove stresa vode. Ovo nije instrukcija za zalivanje."
                    ),
                    reason="Preventivni irrigation monitoring bez sistema.",
                    item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.LOW,
                    priority_reason="Osnovni monitoring bez sistema.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    planned_date_from=date(year, 4, 1),
                    planned_date_to=date(year, 9, 30),
                )
            )
            weather_items, weather_missing = self._weather_items(parcel, owner_id, year, today)
            drafts.extend(weather_items)
            if weather_missing:
                missing.extend(weather_missing)
            return drafts

        # Has irrigation system
        itype = parcel.irrigation_type
        if itype is None:
            missing.append("tip sistema (drip/sprinkler/…)")
        profile_lines = [
            f"Tip: {itype.value if itype else 'nije unet'}.",
            f"Izvor vode: {parcel.water_source or 'nije unet'}.",
            f"Sekcije: {parcel.irrigation_sections if parcel.irrigation_sections is not None else 'nije uneto'}.",
        ]
        if density:
            profile_lines.append(f"Gustina: {density}.")
        if age is not None:
            profile_lines.append(f"Starost zasada: {age} god.")

        drip_like = itype in {IrrigationType.DRIP, IrrigationType.MICROSPRINKLER}
        if drip_like:
            if parcel.emitter_flow_lph is None:
                missing.append("protok emitera (l/h)")
            if parcel.emitter_spacing_m is None:
                missing.append("razmak emitera (m)")
            if parcel.line_count is None:
                missing.append("broj linija")
            profile_lines.extend(
                [
                    f"Protok emitera: {parcel.emitter_flow_lph or 'nedostaje'} l/h.",
                    f"Razmak emitera: {parcel.emitter_spacing_m or 'nedostaje'} m.",
                    f"Broj linija: {parcel.line_count if parcel.line_count is not None else 'nedostaje'}.",
                ]
            )
        elif itype == IrrigationType.SPRINKLER:
            if parcel.irrigation_pressure_bar is None:
                missing.append("pritisak (bar)")
            profile_lines.append(
                f"Pritisak: {parcel.irrigation_pressure_bar or 'nedostaje'} bar."
            )

        drafts.append(
            DraftPlanItem(
                title="Profil sistema za navodnjavanje",
                description=" ".join(profile_lines)
                + (
                    f"\n\nNedostaje: {', '.join(missing)}."
                    if missing
                    else ""
                ),
                reason="Parcel irrigation profile kao ulaz u plan.",
                item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                stream=PlanningStream.PREVENTIVE,
                source=PlanningItemSource.SYSTEM,
                status=PlanningItemStatus.MONITOR,
                priority_level=PlanningPriorityLevel.LOW if not missing else PlanningPriorityLevel.MEDIUM,
                priority_reason=(
                    "Profil kompletan." if not missing else "Profil postoji ali nedostaju tehnički parametri."
                ),
                scope_type=PlanningScopeType.PARCEL,
                scope_id=parcel.id,
                missing_data=list(missing),
            )
        )

        # System calculation when drip params present
        if drip_like and parcel.emitter_flow_lph is not None and parcel.line_count is not None:
            flow = Decimal(str(parcel.emitter_flow_lph))
            lines = Decimal(str(parcel.line_count))
            sections = Decimal(str(parcel.irrigation_sections or 1))
            # Theoretical capacity assumption: one emitter equivalent per line per hour × lines.
            capacity_lph = flow * lines
            assumptions = [
                f"emitter_flow_lph={flow}",
                f"line_count={lines}",
                f"irrigation_sections={sections}",
                "Pretpostavka: protok po liniji ≈ protok emitera (pojednostavljeno).",
                "Procena NIJE precizno merenje na terenu.",
            ]
            drafts.append(
                DraftPlanItem(
                    title="Proračun kapaciteta sistema (model)",
                    description=(
                        f"Procena je zasnovana na: {'; '.join(assumptions)}. "
                        f"Teorijski kapacitet ≈ {capacity_lph} l/h za aktivnu sekciju "
                        f"(bez korekcije efikasnosti"
                        f"{f', efficiency={parcel.irrigation_efficiency}%' if parcel.irrigation_efficiency is not None else ''}).\n\n"
                        "Predlog za stručnu proveru — modelska procena, ne merenje."
                    ),
                    reason="System calculation from declared drip parameters with explicit assumptions.",
                    item_kind=PlanningItemKind.SYSTEM_CALCULATION,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Ima dovoljno parametara za modelski proračun — zahteva review.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    evidence=[
                        {
                            "calculation": "capacity_lph = emitter_flow_lph * line_count",
                            "capacity_lph": float(capacity_lph),
                            "assumptions": assumptions,
                        }
                    ],
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
        elif drip_like and "protok emitera (l/h)" in missing:
            drafts.append(
                DraftPlanItem(
                    title=INSUFFICIENT,
                    description=(
                        "Drip sistem je označen, ali nedostaje protok emitera. "
                        "Sistem ne izmišlja vrednost i ne radi product/dose recommendation."
                    ),
                    reason="Missing emitter_flow — no invented calculation.",
                    item_kind=PlanningItemKind.ASSESSMENT,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.SYSTEM,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Bez emitter flow nema pouzdanog proračuna.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    missing_data=["protok emitera (l/h)"],
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )

        weather_items, weather_missing = self._weather_items(parcel, owner_id, year, today)
        drafts.extend(weather_items)
        if weather_missing:
            missing.extend(weather_missing)

        # Estimated need window when weather available
        if weather_items and not any("vremenska" in m for m in weather_missing):
            area = float(parcel.area_hectares) if parcel.area_hectares else None
            area_note = f"površina {area} ha" if area else "površina nije uneta"
            drafts.append(
                DraftPlanItem(
                    title="Prozor navodnjavanja / procena potrebe",
                    description=(
                        f"Procena je zasnovana na: dostupnoj vremenskoj prognozi, {area_note}, "
                        f"tipu sistema ({itype.value if itype else 'nepoznat'}), "
                        "i (gde postoji) SoilGrids/lab kontekstu. "
                        "Ovo NIJE precizno merenje evapotranspiracije na parceli.\n\n"
                        "Predlog za stručnu proveru."
                    ),
                    reason="Irrigation window + estimated need with labeled assumptions.",
                    item_kind=PlanningItemKind.IRRIGATION_WINDOW,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.PLANNED,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Vremenski uslovi + sistem omogućavaju prozor za procenu.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    planned_date_from=today,
                    planned_date_to=today + timedelta(days=14),
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )
            drafts.append(
                DraftPlanItem(
                    title="Modelska procena potrebe za vodom",
                    description=(
                        "Procena je zasnovana na dostupnim inputima (vreme, površina, sistem). "
                        "Nema inventisanih parametara. "
                        "Modelska procena ≠ precizno merenje.\n\n"
                        "Predlog za stručnu proveru."
                    ),
                    reason="Estimated need item with explicit non-measurement disclaimer.",
                    item_kind=PlanningItemKind.ESTIMATED_NEED,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.MEDIUM,
                    priority_reason="Procena potrebe zahteva expert review.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            )

        # Soil context (lab preferred, SoilGrids secondary)
        verified = self.soil_lab.get_latest_verified(parcel.id)
        if verified is not None:
            drafts.append(
                DraftPlanItem(
                    title="Soil lab kontekst (za navodnjavanje)",
                    description=(
                        f"Verified lab analiza od {verified.sampled_on.isoformat()} "
                        "može biti relevantna za zadržavanje vode / teksturu — "
                        "nije instrukcija za zalivanje."
                    ),
                    reason="Lab soil where relevant for irrigation context.",
                    item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.AGRONOMIC_RULE,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Lab soil je sekundarni kontekst za irrigation.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    evidence=[
                        {
                            "source_kind": "laboratory",
                            "analysis_id": str(verified.id),
                            "sampled_on": verified.sampled_on.isoformat(),
                        }
                    ],
                )
            )
        else:
            soilgrids = self.db.scalar(
                select(SoilProfileSnapshot).where(SoilProfileSnapshot.parcel_id == parcel.id).limit(1)
            )
            if soilgrids is not None:
                drafts.append(
                    DraftPlanItem(
                        title="SoilGrids kontekst (nije lab)",
                        description=(
                            "SoilGrids modelovana procena kao sekundarni context. "
                            "NIJE laboratorijska analiza."
                        ),
                        reason="SoilGrids secondary context for irrigation.",
                        item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.SYSTEM,
                        status=PlanningItemStatus.MONITOR,
                        priority_level=PlanningPriorityLevel.INFO,
                        priority_reason="Modeled soil estimate — informativno.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        evidence=[{"source_kind": "soilgrids", "snapshot_id": str(soilgrids.id)}],
                    )
                )

        # Previous irrigation activities
        drafts.extend(self._previous_irrigation_activities(parcel))

        if include_knowledge and variety:
            evidence, kb_note = knowledge_citations(
                self.db,
                farm_id=parcel.farm_id,
                question=f"Navodnjavanje {variety} leska kap po kap monitoring",
            )
            if evidence:
                drafts.append(
                    DraftPlanItem(
                        title="Agriser kontekst za navodnjavanje",
                        description="Citati iz Agriser priručnika. Predlog za stručnu proveru.",
                        reason="Agriser knowledge for irrigation domain.",
                        item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.AGRONOMIC_RULE,
                        status=PlanningItemStatus.MONITOR,
                        priority_level=PlanningPriorityLevel.LOW,
                        priority_reason="Knowledge citati.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        evidence=evidence,
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )
            elif kb_note:
                drafts.append(
                    DraftPlanItem(
                        title="Nedovoljno Agriser dokaza za navodnjavanje",
                        description=f"{kb_note}\n\n{INSUFFICIENT}",
                        reason="No reliable Agriser evidence.",
                        item_kind=PlanningItemKind.ASSESSMENT,
                        stream=PlanningStream.PREVENTIVE,
                        source=PlanningItemSource.SYSTEM,
                        status=PlanningItemStatus.NEEDS_REVIEW,
                        priority_level=PlanningPriorityLevel.INFO,
                        priority_reason="Nema knowledge podrške.",
                        scope_type=PlanningScopeType.PARCEL,
                        scope_id=parcel.id,
                        missing_data=["Agriser evidence for irrigation"],
                        expert_review_status=PlanningExpertReviewStatus.PENDING,
                    )
                )

        drafts.append(
            DraftPlanItem(
                title="Predlog za stručnu proveru (navodnjavanje)",
                description=(
                    "Modelske procene i prozori navodnjavanja nisu konačna instrukcija. "
                    "Stručna provera pre intervencije."
                ),
                reason="Expert review gate for irrigation conclusions.",
                item_kind=PlanningItemKind.EXPERT_REVIEW,
                stream=PlanningStream.PREVENTIVE,
                source=PlanningItemSource.SYSTEM,
                status=PlanningItemStatus.NEEDS_REVIEW,
                priority_level=PlanningPriorityLevel.MEDIUM,
                priority_reason="Expert review pre intervencije.",
                scope_type=PlanningScopeType.PARCEL,
                scope_id=parcel.id,
                expert_review_status=PlanningExpertReviewStatus.PENDING,
            )
        )

        return drafts

    def _weather_items(
        self,
        parcel: Parcel,
        owner_id: UUID,
        year: int,
        today: date,
    ) -> tuple[list[DraftPlanItem], list[str]]:
        missing: list[str] = []
        try:
            context = season_context(self.db, owner_id, parcel.id)
        except Exception:
            logger.exception("Irrigation weather context failed")
            return [], ["vremenska prognoza"]

        weather = getattr(context, "weather", None)
        if not weather:
            return [
                DraftPlanItem(
                    title="Nedostaju vremenski podaci",
                    description=f"{INSUFFICIENT} Nema keširane vremenske prognoze za parcelu.",
                    reason="Weather missing — no invented rainfall/temperature.",
                    item_kind=PlanningItemKind.ASSESSMENT,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.SYSTEM,
                    status=PlanningItemStatus.NEEDS_REVIEW,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Bez vremena nema pouzdane irrigation procene.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    missing_data=["vremenska prognoza"],
                    expert_review_status=PlanningExpertReviewStatus.PENDING,
                )
            ], ["vremenska prognoza"]

        status = getattr(weather, "status", None)
        is_stale = bool(getattr(weather, "is_stale", False))
        precip = getattr(weather, "precipitation", None)
        avg_temp = getattr(weather, "average_temperature", None)
        message = getattr(weather, "message", None)

        if status and str(status).endswith("missing"):
            missing.append("vremenska prognoza")
        if is_stale:
            missing.append("sveža vremenska prognoza (stale cache)")

        desc_parts = [
            f"Padavine (agregat): {precip if precip is not None else 'nedostaje'} mm.",
            f"Prosečna temperatura: {avg_temp if avg_temp is not None else 'nedostaje'} °C.",
        ]
        if is_stale:
            desc_parts.append("UPOZORENJE: vremenski keš je zastareo (stale) — ne tretira se kao precizno merenje.")
        if message:
            desc_parts.append(str(message)[:240])

        return [
            DraftPlanItem(
                title="Vremenski monitoring za navodnjavanje",
                description=" ".join(desc_parts) + "\n\nPredlog za stručnu proveru.",
                reason="Weather/rainfall/temperature context for irrigation planning.",
                item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                stream=PlanningStream.PREVENTIVE,
                source=PlanningItemSource.AGRONOMIC_RULE,
                status=PlanningItemStatus.MONITOR if not is_stale else PlanningItemStatus.NEEDS_REVIEW,
                priority_level=PlanningPriorityLevel.MEDIUM if is_stale else PlanningPriorityLevel.LOW,
                priority_reason=(
                    "Stale weather — smanjena pouzdanost."
                    if is_stale
                    else "Aktuelni vremenski kontekst za monitoring."
                ),
                scope_type=PlanningScopeType.PARCEL,
                scope_id=parcel.id,
                planned_date_from=today,
                planned_date_to=today + timedelta(days=7),
                missing_data=list(missing),
                evidence=[
                    {
                        "source_kind": "weather",
                        "precipitation": precip,
                        "average_temperature": avg_temp,
                        "is_stale": is_stale,
                        "status": str(status) if status is not None else None,
                    }
                ],
            )
        ], missing

    def _previous_irrigation_activities(self, parcel: Parcel) -> list[DraftPlanItem]:
        stmt = (
            select(Activity)
            .where(
                Activity.parcel_id == parcel.id,
                Activity.semantic_type == ActivitySemanticType.IRRIGATION,
            )
            .order_by(Activity.performed_on.desc(), Activity.created_at.desc())
            .limit(10)
        )
        drafts: list[DraftPlanItem] = []
        for activity in self.db.scalars(stmt).all():
            drafts.append(
                DraftPlanItem(
                    title=f"Istorija zalivanja ({activity.performed_on.isoformat()})",
                    description=(
                        f"HISTORIJSKI KONTEKST — {activity.title}. "
                        "Prethodno zalivanje nije dokaz trenutne potrebe."
                    ),
                    reason="Previous irrigation activities as historical context.",
                    item_kind=PlanningItemKind.IRRIGATION_MONITORING,
                    stream=PlanningStream.PREVENTIVE,
                    source=PlanningItemSource.HISTORY,
                    status=PlanningItemStatus.MONITOR,
                    priority_level=PlanningPriorityLevel.INFO,
                    priority_reason="Istorija zalivanja — informativno.",
                    scope_type=PlanningScopeType.PARCEL,
                    scope_id=parcel.id,
                    related_activity_id=activity.id,
                )
            )
        return drafts
