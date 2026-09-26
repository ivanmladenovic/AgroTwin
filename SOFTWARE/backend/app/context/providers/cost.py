from __future__ import annotations

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult, RankedItem, scope_from_enum, scope_id_for
from app.context.ranking import MIN_KEEP_SCORE, combine_score, match_scope, temporal_relevance
from app.context.temporal import temporal_relation
from app.context.types import ContextRequestType, ContextScope, DataQualityStatus, SourceType, WarningType
from app.models.cost import Cost
from app.repositories.cost import CostRepository
from app.schemas.context import ContextCostItem, ContextCostSummary, ProvenanceRead
from app.services.parcel_report_calc import year_bounds


class CostContextProvider:
    def __init__(self, db: Session) -> None:
        self.costs = CostRepository(db)

    def get_source_type(self) -> str:
        return "costs"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_costs and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        start, end = year_bounds(query.subject.season_year)
        if query.profile.request_type == ContextRequestType.ACTIVITY_ANALYSIS and query.request.activity_id:
            rows = [
                cost
                for cost in self.costs.list_for_owner(
                    query.owner_id,
                    parcel_id=parcel.id,
                    date_from=start,
                    date_to=end,
                )
                if cost.activity_id == query.request.activity_id
            ]
            if query.subject.activity is not None:
                rows = list(query.subject.activity.costs)
        else:
            rows = self.costs.list_for_owner(query.owner_id, parcel_id=parcel.id, date_from=start, date_to=end)

        items: list[RankedItem] = []
        for cost in rows:
            ranked = _rank_cost(cost, query)
            if ranked.relevance_score < MIN_KEEP_SCORE and query.profile.request_type == ContextRequestType.ACTIVITY_ANALYSIS:
                continue
            items.append(ranked)
        items.sort(key=lambda item: (-item.relevance_score, str(item.date)))

        by_category = [
            {"slug": category.slug, "name": category.name, "total": total}
            for category, total in self.costs.totals_by_category(
                query.owner_id, parcel_id=parcel.id, date_from=start, date_to=end
            )
        ]
        by_activity = [
            {"slug": activity_type.slug, "name": activity_type.name, "total": total}
            for activity_type, total in self.costs.totals_by_activity_type(
                query.owner_id, parcel_id=parcel.id, date_from=start, date_to=end
            )
        ]
        total = self.costs.sum_for_owner(query.owner_id, parcel_id=parcel.id, date_from=start, date_to=end)
        status = DataQualityStatus.AVAILABLE if rows or total else DataQualityStatus.MISSING
        warnings = []
        if status == DataQualityStatus.MISSING:
            warnings.append(ContextWarning(WarningType.MISSING_DATA, "costs", "Nema troškova za izabrani period."))
        selected_items = [
            item.payload
            for item in items
            if query.profile.request_type == ContextRequestType.ACTIVITY_ANALYSIS
        ]
        payload = ContextCostSummary(
            status=status,
            total=total if rows or total else None,
            by_category=by_category,
            by_activity_type=by_activity,
            period_start=start,
            period_end=end,
            scope="PARCEL",
            items=selected_items,
        )
        return ProviderResult(
            source="costs",
            source_type=SourceType.USER_RECORD.value,
            status=status,
            items=items if query.profile.request_type == ContextRequestType.ACTIVITY_ANALYSIS else [],
            payload=payload,
            collected=len(rows),
            filtered=0,
            warnings=warnings,
        )


def _rank_cost(cost: Cost, query: EngineQuery) -> RankedItem:
    scope = scope_from_enum(cost.scope_type)
    recorded = ContextScope(scope)
    _, scope_score, scope_reason = match_scope(
        subject_tree_id=query.subject.tree.id if query.subject.tree else None,
        subject_row_id=query.subject.row.id if query.subject.row else None,
        subject_parcel_id=query.subject.parcel.id if query.subject.parcel else None,
        item_tree_id=cost.tree_id,
        item_row_id=cost.row_id,
        item_parcel_id=cost.parcel_id,
        recorded_scope=recorded,
    )
    time_score, time_reason = temporal_relevance(cost.incurred_on, query.subject.event_date)
    type_score = 1.0 if query.request.activity_id == cost.activity_id else 0.5
    score = combine_score(query.profile.request_type, scope_score, time_score, type_score)
    relation = temporal_relation(cost.incurred_on, query.subject.event_date)
    scope_id = scope_id_for(scope, farm_id=cost.farm_id, parcel_id=cost.parcel_id, row_id=cost.row_id, tree_id=cost.tree_id)
    slug = cost.cost_category.slug if cost.cost_category else "other"
    provenance = ProvenanceRead(
        source="cost",
        source_id=str(cost.id),
        source_type=SourceType.USER_RECORD.value,
        scope=scope,
        scope_id=scope_id,
        recorded_at=cost.incurred_on,
        retrieved_at=query.retrieved_at,
        relevance_score=score,
    )
    payload = ContextCostItem(
        id=cost.id,
        amount=cost.amount,
        currency=cost.currency,
        incurred_on=cost.incurred_on,
        description=cost.description,
        category=slug,
        activity_id=cost.activity_id,
        scope=scope,
        scope_id=scope_id,
        relevance_score=score,
        provenance=provenance,
    )
    return RankedItem(
        kind="cost",
        id=str(cost.id),
        payload=payload,
        relevance_score=score,
        reasons=[scope_reason, time_reason],
        scope=scope,
        date=cost.incurred_on,
        temporal_relation=relation.value,
    )
