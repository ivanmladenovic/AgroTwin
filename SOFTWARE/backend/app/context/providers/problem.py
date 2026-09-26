from __future__ import annotations

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult, RankedItem, scope_id_for
from app.context.ranking import MIN_KEEP_SCORE, combine_score, match_scope, temporal_relevance
from app.context.temporal import temporal_relation
from app.context.types import ContextScope, DataQualityStatus, SourceType, WarningType
from app.models.disease import DiseaseCase
from app.repositories.disease import DiseaseRepository
from app.schemas.context import ContextProblemItem, ProvenanceRead


class ProblemContextProvider:
    def __init__(self, db: Session) -> None:
        self.diseases = DiseaseRepository(db)

    def get_source_type(self) -> str:
        return "problems"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_problems and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        rows = self.diseases.list_for_owner(query.owner_id, parcel_id=parcel.id)
        items: list[RankedItem] = []
        for case in rows:
            ranked = _rank_problem(case, query)
            if ranked.relevance_score < MIN_KEEP_SCORE and query.request.disease_case_id != case.id:
                continue
            items.append(ranked)
        items.sort(key=lambda item: (-item.relevance_score, str(item.date)))
        warnings = []
        status = DataQualityStatus.AVAILABLE if items else DataQualityStatus.MISSING
        if not items:
            warnings.append(ContextWarning(WarningType.MISSING_DATA, "problems", "Nema prijavljenih problema za ovaj predmet."))
        return ProviderResult(
            source="problems",
            source_type=SourceType.USER_RECORD.value,
            status=status,
            items=items,
            collected=len(rows),
            filtered=len(rows) - len(items),
            warnings=warnings,
        )


def _rank_problem(case: DiseaseCase, query: EngineQuery) -> RankedItem:
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
    time_score, time_reason = temporal_relevance(case.detected_on, query.subject.event_date)
    type_score = 1.0 if query.request.disease_case_id == case.id else 0.8
    score = combine_score(query.profile.request_type, scope_score, time_score, type_score)
    if query.request.disease_case_id == case.id:
        score = 1.0
    relation = temporal_relation(case.detected_on, query.subject.event_date)
    scope = recorded.value
    scope_id = scope_id_for(scope, farm_id=case.farm_id, parcel_id=case.parcel_id, row_id=case.row_id, tree_id=case.tree_id)
    provenance = ProvenanceRead(
        source="disease_case",
        source_id=str(case.id),
        source_type=SourceType.USER_RECORD.value,
        scope=scope,
        scope_id=scope_id,
        recorded_at=case.detected_on,
        retrieved_at=query.retrieved_at,
        relevance_score=score,
    )
    payload = ContextProblemItem(
        id=case.id,
        title=case.title,
        category=case.category.value,
        severity=case.severity.value,
        status=case.status.value,
        detected_on=case.detected_on,
        description=case.description,
        scope=scope,
        scope_id=scope_id,
        temporal_relation=relation,
        relevance_score=score,
        provenance=provenance,
    )
    reasons = [scope_reason, time_reason]
    if query.request.disease_case_id == case.id:
        reasons.insert(0, "focus problem")
    return RankedItem(
        kind="problem",
        id=str(case.id),
        payload=payload,
        relevance_score=score,
        reasons=reasons,
        scope=scope,
        date=case.detected_on,
        temporal_relation=relation.value,
    )
