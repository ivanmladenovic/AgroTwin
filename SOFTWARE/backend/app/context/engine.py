"""Central Context Engine. Deterministic, explainable, no LLM."""

from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.context.profiles import get_profile
from app.context.providers.activity import ActivityContextProvider
from app.context.providers.ai_history import AIHistoryContextProvider
from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult, RankedItem
from app.context.providers.cost import CostContextProvider
from app.context.providers.harvest import HarvestContextProvider
from app.context.providers.photo import PhotoContextProvider
from app.context.providers.problem import ProblemContextProvider
from app.context.providers.soil import SoilContextProvider
from app.context.providers.weather import WeatherContextProvider
from app.context.request import ContextRequest, ResolvedSubject
from app.context.subject import SubjectResolver
from app.context.types import CONTEXT_VERSION, DataQualityStatus, SourceType, WarningType
from app.core.exceptions import AppError
from app.repositories.parcel import ParcelRepository
from app.schemas.context import (
    AgroTwinContext,
    ContextCropRead,
    ContextDebugRead,
    ContextFarmRead,
    ContextKnowledgeQuery,
    ContextParcelRead,
    ContextRequestEcho,
    ContextRowRead,
    ContextSubjectRead,
    ContextTreeRead,
    ContextWarningRead,
    DataQualityMap,
    DebugRecordRead,
    ProvenanceRead,
)

logger = logging.getLogger("agrotwin.context")

_CRITICAL_PROVIDERS = set()


class ContextEngine:
    def __init__(self, db: Session, providers: list | None = None) -> None:
        self.db = db
        self.parcels = ParcelRepository(db)
        self.resolver = SubjectResolver(db)
        self.providers = providers or [
            ActivityContextProvider(db),
            CostContextProvider(db),
            WeatherContextProvider(db),
            SoilContextProvider(db),
            HarvestContextProvider(db),
            PhotoContextProvider(db),
            AIHistoryContextProvider(db),
            ProblemContextProvider(db),
        ]

    def build_context(self, owner_id, request: ContextRequest) -> AgroTwinContext:
        started = time.perf_counter()
        profile = get_profile(request.request_type)
        subject = self.resolver.resolve(owner_id, request)
        if request.request_type.value == "ACTIVITY_ANALYSIS" and request.activity_id is None and subject.activity is None:
            raise AppError("ACTIVITY_ANALYSIS zahteva activity_id", 400)
        query = EngineQuery(owner_id=owner_id, request=request, subject=subject, profile=profile)
        results: dict[str, ProviderResult] = {}
        failures: list[dict[str, str]] = []
        used: list[str] = []
        for provider in self.providers:
            source = provider.get_source_type()
            if not provider.supports(query):
                continue
            used.append(source)
            try:
                results[source] = provider.collect(query)
            except Exception as exc:
                logger.warning("context provider failed source=%s error=%s", source, exc.__class__.__name__)
                failures.append({"source": source, "error": exc.__class__.__name__})
                results[source] = ProviderResult(
                    source=source,
                    source_type="error",
                    status=DataQualityStatus.ERROR,
                    warnings=[
                        ContextWarning(
                            WarningType.SOURCE_ERROR,
                            source,
                            _provider_error_message(source),
                        )
                    ],
                )
                if source in _CRITICAL_PROVIDERS:
                    raise

        selected_map, excluded_map = _apply_budgets(results, profile)
        warnings = _collect_warnings(results)
        quality = _data_quality(profile, results)
        provenance = _collect_provenance(selected_map)
        activities = [item.payload for item in selected_map.get("activities", [])]
        photos = [item.payload for item in selected_map.get("photos", [])]
        analyses = [item.payload for item in selected_map.get("previous_ai_analyses", [])]
        problems = [item.payload for item in selected_map.get("problems", [])]
        harvest_result = results.get("harvest")
        cost_result = results.get("costs")
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.info(
            "context_built request_type=%s subject=%s providers=%s duration_ms=%s collected=%s selected=%s failures=%s",
            request.request_type.value,
            subject.type,
            ",".join(used),
            duration_ms,
            {key: result.collected for key, result in results.items()},
            {key: len(items) for key, items in selected_map.items()},
            [item["source"] for item in failures],
        )
        debug = None
        if request.include_debug:
            debug = _debug_payload(
                used,
                failures,
                results,
                selected_map,
                excluded_map,
                duration_ms,
                profile.budget.max_excluded_debug,
            )
        return AgroTwinContext(
            context_id=uuid4(),
            context_version=CONTEXT_VERSION,
            created_at=datetime.now(timezone.utc),
            request=_echo(request, subject),
            subject=_subject_dto(subject, self.parcels.tree_count(subject.parcel.id) if subject.parcel else 0),
            crop=_crop_dto(subject),
            soil=results["soil"].payload if "soil" in results else None,
            weather=results["weather"].payload if "weather" in results else None,
            activities=activities,
            activity_summary=_activity_summary(results.get("activities")) if profile.summarize_activities else None,
            costs=cost_result.payload if cost_result is not None else None,
            harvest=harvest_result.payload if harvest_result is not None else None,
            photos=photos,
            previous_ai_analyses=analyses,
            problems=problems,
            knowledge_query=_knowledge_query(request, activities, problems),
            data_quality=quality,
            warnings=[ContextWarningRead(type=item.type, source=item.source, message=item.message) for item in warnings],
            provenance=provenance,
            debug=debug,
        )


def _apply_budgets(results: dict[str, ProviderResult], profile) -> tuple[dict[str, list[RankedItem]], dict[str, list[RankedItem]]]:
    limits = {
        "activities": profile.budget.max_activities,
        "photos": profile.budget.max_photos,
        "previous_ai_analyses": profile.budget.max_ai_analyses,
        "harvest": profile.budget.max_harvest_events,
        "problems": profile.budget.max_problems,
    }
    selected: dict[str, list[RankedItem]] = {}
    excluded: dict[str, list[RankedItem]] = {}
    for source, result in results.items():
        items = list(result.items)
        limit = limits.get(source)
        if limit is None:
            selected[source] = items
            excluded[source] = []
            continue
        selected[source] = items[:limit]
        excluded[source] = items[limit:]
        result.filtered += len(excluded[source])
    return selected, excluded


def _collect_warnings(results: dict[str, ProviderResult]) -> list[ContextWarning]:
    warnings: list[ContextWarning] = []
    for result in results.values():
        warnings.extend(result.warnings)
    return warnings


def _data_quality(profile, results: dict[str, ProviderResult]) -> DataQualityMap:
    def status_for(source: str, included: bool) -> DataQualityStatus | None:
        if not included:
            return None
        result = results.get(source)
        if result is None:
            return DataQualityStatus.MISSING
        return result.status

    return DataQualityMap(
        parcel=DataQualityStatus.AVAILABLE,
        soil=status_for("soil", profile.include_soil) or DataQualityStatus.MISSING,
        weather=status_for("weather", profile.include_weather) or DataQualityStatus.MISSING,
        activities=status_for("activities", profile.include_activities) or DataQualityStatus.MISSING,
        costs=status_for("costs", profile.include_costs),
        harvest=status_for("harvest", profile.include_harvest),
        photos=status_for("photos", profile.include_photos) or DataQualityStatus.MISSING,
        previous_ai_analyses=status_for("previous_ai_analyses", profile.include_ai) or DataQualityStatus.MISSING,
        problems=status_for("problems", profile.include_problems),
    )


def _collect_provenance(selected: dict[str, list[RankedItem]]) -> list[ProvenanceRead]:
    items: list[ProvenanceRead] = []
    for rows in selected.values():
        for row in rows:
            payload = row.payload
            provenance = getattr(payload, "provenance", None)
            if isinstance(provenance, ProvenanceRead):
                items.append(provenance)
    return items


def _echo(request: ContextRequest, subject: ResolvedSubject) -> ContextRequestEcho:
    return ContextRequestEcho(
        type=request.request_type,
        query=request.query,
        season_year=subject.season_year,
        event_date=subject.event_date,
        parcel_id=request.parcel_id or (subject.parcel.id if subject.parcel else None),
        row_id=request.row_id or (subject.row.id if subject.row else None),
        tree_id=request.tree_id or (subject.tree.id if subject.tree else None),
        photo_id=request.photo_id,
        activity_id=request.activity_id,
        disease_case_id=request.disease_case_id,
    )


def _subject_dto(subject: ResolvedSubject, tree_count: int) -> ContextSubjectRead:
    farm = subject.farm
    parcel = subject.parcel
    row = subject.row
    tree = subject.tree
    return ContextSubjectRead(
        type=subject.type,
        farm=ContextFarmRead(
            id=farm.id,
            name=farm.name,
            location_name=farm.location_name,
            latitude=farm.latitude,
            longitude=farm.longitude,
        ),
        parcel=ContextParcelRead(
            id=parcel.id,
            name=parcel.name,
            code=parcel.code,
            area_hectares=parcel.area_hectares,
            latitude=parcel.latitude,
            longitude=parcel.longitude,
            altitude=parcel.altitude,
            row_count=parcel.row_count,
            trees_per_row=parcel.trees_per_row,
            row_spacing_m=parcel.row_spacing_m,
            tree_spacing_m=parcel.tree_spacing_m,
            default_variety=parcel.default_variety,
            varieties=list(parcel.varieties or []),
            default_planting_year=parcel.default_planting_year,
            tree_count=tree_count,
            notes=parcel.notes,
            has_boundary=parcel.boundary is not None,
        )
        if parcel
        else None,
        row=ContextRowRead(
            id=row.id,
            row_number=row.row_number,
            name=row.name,
            variety=row.variety,
            tree_count=row.tree_count,
            parcel_id=row.parcel_id,
        )
        if row
        else None,
        tree=ContextTreeRead(
            id=tree.id,
            public_id=tree.public_id,
            row_id=tree.row_id,
            parcel_id=tree.parcel_id,
            position_in_row=tree.position_in_row,
            variety=tree.variety,
            planting_year=tree.planting_year,
            status=tree.status.value,
            health_status=tree.health_status.value,
            notes=tree.notes,
            latitude=tree.latitude,
            longitude=tree.longitude,
        )
        if tree
        else None,
    )


def _crop_dto(subject: ResolvedSubject) -> ContextCropRead:
    tree = subject.tree
    parcel = subject.parcel
    variety = (tree.variety if tree and tree.variety else None) or (parcel.default_variety if parcel else None)
    planting_year = (tree.planting_year if tree and tree.planting_year else None) or (
        parcel.default_planting_year if parcel else None
    )
    age = None
    if planting_year:
        age = max(0, subject.event_date.year - planting_year)
    return ContextCropRead(
        variety=variety,
        varieties=list(parcel.varieties or []) if parcel else [],
        planting_year=planting_year,
        age_years=age,
    )


def _activity_summary(result: ProviderResult | None) -> dict | None:
    if result is None:
        return None
    counts = Counter(item.payload.type for item in result.items)
    return {
        "count": len(result.items),
        "by_type": [{"type": key, "count": value} for key, value in counts.most_common()],
        "source_type": SourceType.DERIVED_SUMMARY.value,
    }


def _knowledge_query(request: ContextRequest, activities, problems) -> ContextKnowledgeQuery:
    topics: list[str] = []
    for item in problems:
        if item.category and item.category not in topics:
            topics.append(item.category)
    for item in activities[:8]:
        if item.type and item.type not in topics:
            topics.append(item.type)
    return ContextKnowledgeQuery(problem=request.query, topics=topics)


def _debug_payload(used, failures, results, selected, excluded, duration_ms, max_excluded) -> ContextDebugRead:
    records: list[DebugRecordRead] = []
    for source, items in selected.items():
        for item in items:
            records.append(
                DebugRecordRead(
                    kind=item.kind,
                    id=item.id,
                    scope=item.scope,
                    date=item.date,
                    relevance_score=item.relevance_score,
                    selected=True,
                    reasons=item.reasons,
                    temporal_relation=item.temporal_relation,
                )
            )
    leftover = 0
    for source, items in excluded.items():
        for item in items:
            if leftover >= max_excluded:
                break
            records.append(
                DebugRecordRead(
                    kind=item.kind,
                    id=item.id,
                    scope=item.scope,
                    date=item.date,
                    relevance_score=item.relevance_score,
                    selected=False,
                    reasons=item.reasons + ["excluded by budget"],
                    temporal_relation=item.temporal_relation,
                )
            )
            leftover += 1
    return ContextDebugRead(
        providers_used=used,
        provider_failures=failures,
        collected={key: result.collected for key, result in results.items()},
        filtered={key: result.filtered for key, result in results.items()},
        selected={key: len(items) for key, items in selected.items()},
        duration_ms=duration_ms,
        records=records,
    )


def _provider_error_message(source: str) -> str:
    labels = {
        "soil": "SoilGrids podaci trenutno nisu dostupni.",
        "weather": "Vremenski podaci trenutno nisu dostupni.",
        "photos": "Fotografije trenutno nisu dostupne.",
        "activities": "Aktivnosti trenutno nisu dostupne.",
        "costs": "Troškovi trenutno nisu dostupni.",
        "harvest": "Podaci o berbi trenutno nisu dostupni.",
        "previous_ai_analyses": "Prethodne AI analize trenutno nisu dostupne.",
        "problems": "Prijave problema trenutno nisu dostupne.",
    }
    return labels.get(source, f"Izvor {source} trenutno nije dostupan.")
