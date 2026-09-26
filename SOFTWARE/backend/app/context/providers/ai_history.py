from __future__ import annotations

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult, RankedItem, scope_id_for
from app.context.ranking import MIN_KEEP_SCORE, combine_score, match_scope, temporal_relevance
from app.context.temporal import temporal_relation
from app.context.types import ContextScope, DataQualityStatus, SourceType, WarningType
from app.repositories.ai import AnalysisRepository
from app.schemas.context import ContextAIItem, ProvenanceRead


class AIHistoryContextProvider:
    def __init__(self, db: Session) -> None:
        self.analyses = AnalysisRepository(db)

    def get_source_type(self) -> str:
        return "previous_ai_analyses"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_ai and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        rows = self.analyses.list_for_parcel(query.owner_id, parcel.id)
        items: list[RankedItem] = []
        for analysis, case in rows:
            ranked = _rank_analysis(analysis, case, query)
            if ranked.relevance_score < MIN_KEEP_SCORE:
                continue
            items.append(ranked)
        items.sort(key=lambda item: (-item.relevance_score, str(item.date)))
        warnings = []
        status = DataQualityStatus.AVAILABLE if items else DataQualityStatus.MISSING
        if not items:
            warnings.append(
                ContextWarning(
                    WarningType.MISSING_DATA,
                    "previous_ai_analyses",
                    "Nema prethodnih AI analiza za ovaj predmet.",
                )
            )
        return ProviderResult(
            source="previous_ai_analyses",
            source_type=SourceType.PREVIOUS_AI_ANALYSIS.value,
            status=status,
            items=items,
            collected=len(rows),
            filtered=len(rows) - len(items),
            warnings=warnings,
        )


def _rank_analysis(analysis, case, query: EngineQuery) -> RankedItem:
    if case.tree_id:
        recorded = ContextScope.TREE
    elif case.row_id:
        recorded = ContextScope.ROW
    else:
        recorded = ContextScope.PARCEL
    matched, scope_score, scope_reason = match_scope(
        subject_tree_id=query.subject.tree.id if query.subject.tree else None,
        subject_row_id=query.subject.row.id if query.subject.row else None,
        subject_parcel_id=query.subject.parcel.id if query.subject.parcel else None,
        item_tree_id=case.tree_id,
        item_row_id=case.row_id,
        item_parcel_id=case.parcel_id,
        recorded_scope=recorded,
    )
    analysis_date = analysis.created_at.date() if analysis.created_at else query.subject.event_date
    time_score, time_reason = temporal_relevance(analysis_date, query.subject.event_date)
    type_score = 1.0
    reasons = [scope_reason, time_reason, "source_type previous_ai_analysis"]
    if query.request.photo_id and analysis.photo_id == query.request.photo_id:
        type_score = 1.0
        reasons.insert(0, "same photo")
        scope_score = max(scope_score, 1.0)
    score = combine_score(query.profile.request_type, scope_score, time_score, type_score)
    relation = temporal_relation(analysis_date, query.subject.event_date)
    scope = matched.value
    scope_id = scope_id_for(
        scope,
        farm_id=case.farm_id,
        parcel_id=case.parcel_id,
        row_id=case.row_id,
        tree_id=case.tree_id,
    )
    provenance = ProvenanceRead(
        source="AgroTwin AI",
        source_id=str(analysis.id),
        source_type=SourceType.PREVIOUS_AI_ANALYSIS.value,
        scope=scope,
        scope_id=scope_id,
        recorded_at=analysis.created_at,
        retrieved_at=query.retrieved_at,
        relevance_score=score,
    )
    payload = ContextAIItem(
        id=analysis.id,
        date=analysis.created_at,
        finding=analysis.likely_issue,
        confidence=analysis.confidence,
        source_type="previous_ai_analysis",
        observed_symptoms=list(analysis.observed_symptoms or []),
        observed_facts=analysis.observed_facts,
        uncertainty_notes=analysis.uncertainty_notes,
        photo_id=analysis.photo_id,
        disease_case_id=analysis.disease_case_id,
        scope=scope,
        scope_id=scope_id,
        provider=analysis.provider,
        model=analysis.model,
        temporal_relation=relation,
        relevance_score=score,
        provenance=provenance,
    )
    return RankedItem(
        kind="previous_ai_analysis",
        id=str(analysis.id),
        payload=payload,
        relevance_score=score,
        reasons=reasons,
        scope=scope,
        date=analysis.created_at,
        temporal_relation=relation.value,
    )
