from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.context.profiles import ContextProfile
from app.context.providers.base import (
    ContextWarning,
    EngineQuery,
    ProviderResult,
    RankedItem,
    scope_from_enum,
    scope_id_for,
)
from app.context.ranking import (
    MIN_KEEP_SCORE,
    activity_type_relevance,
    combine_score,
    match_scope,
    temporal_relevance,
)
from app.context.temporal import temporal_relation
from app.context.types import ContextScope, DataQualityStatus, SourceType, WarningType
from app.models.activity import Activity
from app.repositories.activity import ActivityRepository
from app.schemas.context import ContextActivityItem, ProvenanceRead
from app.services.parcel_report_calc import year_bounds


class ActivityContextProvider:
    def __init__(self, db: Session) -> None:
        self.activities = ActivityRepository(db)

    def get_source_type(self) -> str:
        return "activities"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_activities and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        date_from, date_to = _activity_window(query.profile, query.subject.event_date, query.subject.season_year)
        rows = self.activities.list_overlapping_scope(
            query.owner_id,
            parcel_id=parcel.id,
            row_id=query.subject.row.id if query.subject.row else None,
            tree_id=query.subject.tree.id if query.subject.tree else None,
            date_from=date_from,
            date_to=date_to,
            include_activity_id=query.request.activity_id,
        )
        items: list[RankedItem] = []
        for activity in rows:
            ranked = _rank_activity(activity, query)
            if ranked.relevance_score < MIN_KEEP_SCORE and query.request.activity_id != activity.id:
                continue
            items.append(ranked)
        items.sort(key=lambda item: (-item.relevance_score, str(item.date)))
        status = DataQualityStatus.AVAILABLE if items else DataQualityStatus.MISSING
        warnings = []
        if not items:
            warnings.append(
                ContextWarning(
                    WarningType.MISSING_DATA,
                    "activities",
                    "Nema aktivnosti u izabranom vremenskom prozoru.",
                )
            )
        return ProviderResult(
            source="activities",
            source_type=SourceType.USER_RECORD.value,
            status=status,
            items=items,
            collected=len(rows),
            filtered=len(rows) - len(items),
            warnings=warnings,
        )


def _activity_window(profile: ContextProfile, event_date, season_year: int):
    if profile.request_type.value in {"PARCEL_ANALYSIS", "SEASON_ANALYSIS"}:
        start, end = year_bounds(season_year)
        return start, end
    days = profile.older_activity_days or profile.recent_activity_days
    return event_date - timedelta(days=days), event_date + timedelta(days=7)


def _rank_activity(activity: Activity, query: EngineQuery) -> RankedItem:
    recorded_scope = ContextScope(scope_from_enum(activity.scope_type))
    matched_scope, scope_score, scope_reason = match_scope(
        subject_tree_id=query.subject.tree.id if query.subject.tree else None,
        subject_row_id=query.subject.row.id if query.subject.row else None,
        subject_parcel_id=query.subject.parcel.id if query.subject.parcel else None,
        item_tree_id=activity.tree_id,
        item_row_id=activity.row_id,
        item_parcel_id=activity.parcel_id,
        extra_row_ids=list(activity.extra_row_ids or []),
        recorded_scope=recorded_scope,
    )
    time_score, time_reason = temporal_relevance(activity.performed_on, query.subject.event_date)
    slug = activity.activity_type.slug if activity.activity_type else "other"
    focus_slug = None
    if query.subject.activity is not None and query.subject.activity.activity_type:
        focus_slug = query.subject.activity.activity_type.slug
    type_score, type_reason = activity_type_relevance(query.profile.request_type, slug, focus_slug=focus_slug)
    score = combine_score(query.profile.request_type, scope_score, time_score, type_score)
    relation = temporal_relation(activity.performed_on, query.subject.event_date)
    scope = recorded_scope.value
    scope_id = scope_id_for(
        scope,
        farm_id=activity.farm_id,
        parcel_id=activity.parcel_id,
        row_id=activity.row_id,
        tree_id=activity.tree_id,
    )
    provenance = ProvenanceRead(
        source="activity",
        source_id=str(activity.id),
        source_type=SourceType.USER_RECORD.value,
        scope=scope,
        scope_id=scope_id,
        recorded_at=activity.performed_on,
        retrieved_at=query.retrieved_at,
        relevance_score=score,
    )
    payload = ContextActivityItem(
        id=activity.id,
        type=slug,
        title=activity.title,
        date=activity.performed_on,
        scope=scope,
        scope_id=scope_id,
        status=activity.status.value,
        quantity=activity.quantity,
        unit=activity.unit,
        notes=activity.notes,
        temporal_relation=relation,
        relevance_score=score,
        provenance=provenance,
    )
    reasons = [scope_reason, time_reason, type_reason, f"recorded scope {scope}"]
    if query.request.activity_id == activity.id:
        reasons.insert(0, "focus activity")
        payload.relevance_score = max(payload.relevance_score, 1.0)
        score = 1.0
    return RankedItem(
        kind="activity",
        id=str(activity.id),
        payload=payload,
        relevance_score=score,
        reasons=reasons,
        scope=scope,
        date=activity.performed_on,
        temporal_relation=relation.value,
    )
