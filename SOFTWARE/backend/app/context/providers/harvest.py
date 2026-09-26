from __future__ import annotations

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult, RankedItem, scope_from_enum, scope_id_for
from app.context.ranking import MIN_KEEP_SCORE, combine_score, match_scope, temporal_relevance
from app.context.temporal import temporal_relation
from app.context.types import ContextRequestType, ContextScope, DataQualityStatus, SourceType, WarningType
from app.models.harvest import HarvestEvent
from app.repositories.harvest import HarvestRepository
from app.schemas.context import ContextHarvestItem, ContextHarvestRead, ProvenanceRead
from app.services.harvest_calc import HarvestMeasure, first_last_dates, parcel_scope_only, total_kg
from app.services.parcel_report_calc import year_bounds


class HarvestContextProvider:
    def __init__(self, db: Session) -> None:
        self.harvests = HarvestRepository(db)

    def get_source_type(self) -> str:
        return "harvest"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_harvest and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        start, end = year_bounds(query.subject.season_year)
        rows = self.harvests.list_for_parcel(query.owner_id, parcel.id, date_from=start, date_to=end)
        items: list[RankedItem] = []
        for event in rows:
            ranked = _rank_harvest(event, query)
            if query.profile.request_type == ContextRequestType.PHOTO_ANALYSIS:
                continue
            if ranked.relevance_score < MIN_KEEP_SCORE and query.profile.request_type == ContextRequestType.PROBLEM_ANALYSIS:
                continue
            items.append(ranked)
        items.sort(key=lambda item: (-item.relevance_score, str(item.date)))
        measures = [
            HarvestMeasure(
                scope_type=event.scope_type.value,
                harvested_on=event.harvested_on,
                gross=event.gross_quantity,
                loss=event.loss_quantity,
                unit=event.unit,
                moisture_percent=event.moisture_percent,
                damaged_percent=event.damaged_percent,
                empty_nuts_percent=event.empty_nuts_percent,
                foreign_material_percent=event.foreign_material_percent,
                quality_category=event.quality_category,
                row_id=event.row_id,
                tree_id=event.tree_id,
            )
            for event in rows
        ]
        parcel_measures = parcel_scope_only(measures)
        first, last = first_last_dates(parcel_measures or measures)
        status = DataQualityStatus.AVAILABLE if rows else DataQualityStatus.MISSING
        warnings = []
        if status == DataQualityStatus.MISSING:
            warnings.append(ContextWarning(WarningType.MISSING_DATA, "harvest", "Nema berbe za izabranu sezonu."))
        payload = ContextHarvestRead(
            status=status,
            event_count=len(rows),
            gross_quantity=total_kg(parcel_measures, "gross"),
            loss_quantity=total_kg(parcel_measures, "loss"),
            net_quantity=total_kg(parcel_measures, "net"),
            first_harvest_on=first,
            last_harvest_on=last,
            items=[item.payload for item in items[: query.profile.budget.max_harvest_events]],
        )
        return ProviderResult(
            source="harvest",
            source_type=SourceType.USER_RECORD.value,
            status=status,
            items=items,
            payload=payload,
            collected=len(rows),
            filtered=max(0, len(items) - query.profile.budget.max_harvest_events),
            warnings=warnings,
        )


def _rank_harvest(event: HarvestEvent, query: EngineQuery) -> RankedItem:
    scope = scope_from_enum(event.scope_type)
    recorded = ContextScope(scope)
    _, scope_score, scope_reason = match_scope(
        subject_tree_id=query.subject.tree.id if query.subject.tree else None,
        subject_row_id=query.subject.row.id if query.subject.row else None,
        subject_parcel_id=query.subject.parcel.id if query.subject.parcel else None,
        item_tree_id=event.tree_id,
        item_row_id=event.row_id,
        item_parcel_id=event.parcel_id,
        recorded_scope=recorded,
    )
    time_score, time_reason = temporal_relevance(event.harvested_on, query.subject.event_date)
    score = combine_score(query.profile.request_type, scope_score, time_score, 0.55)
    relation = temporal_relation(event.harvested_on, query.subject.event_date)
    scope_id = scope_id_for(scope, farm_id=event.farm_id, parcel_id=event.parcel_id, row_id=event.row_id, tree_id=event.tree_id)
    provenance = ProvenanceRead(
        source="harvest",
        source_id=str(event.id),
        source_type=SourceType.USER_RECORD.value,
        scope=scope,
        scope_id=scope_id,
        recorded_at=event.harvested_on,
        retrieved_at=query.retrieved_at,
        relevance_score=score,
    )
    payload = ContextHarvestItem(
        id=event.id,
        harvested_on=event.harvested_on,
        gross_quantity=event.gross_quantity,
        loss_quantity=event.loss_quantity,
        net_quantity=event.net_quantity,
        unit=event.unit,
        quality_category=event.quality_category.value if event.quality_category else None,
        moisture_percent=event.moisture_percent,
        damaged_percent=event.damaged_percent,
        empty_nuts_percent=event.empty_nuts_percent,
        scope=scope,
        scope_id=scope_id,
        temporal_relation=relation,
        relevance_score=score,
        provenance=provenance,
    )
    return RankedItem(
        kind="harvest",
        id=str(event.id),
        payload=payload,
        relevance_score=score,
        reasons=[scope_reason, time_reason],
        scope=scope,
        date=event.harvested_on,
        temporal_relation=relation.value,
    )
