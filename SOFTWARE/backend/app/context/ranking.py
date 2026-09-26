"""Deterministic relevance ranking for Context Engine V1.

The engine never uses embeddings or an LLM. Scores are a weighted sum of:

1. scope_relevance  — how closely the record matches the request subject
2. temporal_relevance — how close the record date is to the event/season
3. type_relevance — whether the activity/photo/analysis kind fits the request

Final score is clamped to [0, 1] and rounded to 3 decimals so it is
reproducible and explainable.

Typical order (PHOTO / PROBLEM):

    same tree + recent
  > same row + recent
  > same parcel + recent
  > same tree + old
  > same parcel + old
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.context.types import ContextRequestType, ContextScope

SCOPE_SCORE = {
    ContextScope.TREE: 1.0,
    ContextScope.ROW: 0.72,
    ContextScope.PARCEL: 0.45,
    ContextScope.FARM: 0.2,
    ContextScope.GLOBAL: 0.1,
    ContextScope.GLOBAL_KNOWLEDGE: 0.1,
}

PHOTO_PROBLEM_ACTIVITY_TYPE = {
    "spraying": 1.0,
    "disease_treatment": 1.0,
    "inspection": 0.95,
    "fertilization": 0.9,
    "irrigation": 0.85,
    "pruning": 0.8,
    "soil_analysis": 0.75,
    "planting": 0.5,
    "tree_replacement": 0.5,
    "maintenance": 0.4,
    "tree_removal": 0.35,
    "harvesting": 0.3,
    "other": 0.3,
}

PARCEL_SEASON_ACTIVITY_TYPE = {
    "harvesting": 1.0,
    "fertilization": 0.9,
    "spraying": 0.85,
    "pruning": 0.85,
    "irrigation": 0.8,
    "soil_analysis": 0.75,
    "disease_treatment": 0.7,
    "inspection": 0.65,
    "planting": 0.6,
    "maintenance": 0.55,
    "tree_replacement": 0.5,
    "tree_removal": 0.45,
    "other": 0.4,
}

WEIGHTS: dict[ContextRequestType, tuple[float, float, float]] = {
    ContextRequestType.PHOTO_ANALYSIS: (0.45, 0.40, 0.15),
    ContextRequestType.PROBLEM_ANALYSIS: (0.45, 0.40, 0.15),
    ContextRequestType.PARCEL_ANALYSIS: (0.30, 0.50, 0.20),
    ContextRequestType.SEASON_ANALYSIS: (0.25, 0.55, 0.20),
    ContextRequestType.ACTIVITY_ANALYSIS: (0.35, 0.35, 0.30),
}

MIN_KEEP_SCORE = 0.18


def clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def temporal_relevance(record_date: date | None, event_date: date) -> tuple[float, str]:
    if record_date is None:
        return 0.25, "missing date"
    delta = abs((event_date - record_date).days)
    if delta <= 7:
        return 1.0, "within 7 days"
    if delta <= 30:
        return 0.85, "within 30 days"
    if delta <= 90:
        return 0.65, "within 90 days"
    if delta <= 180:
        return 0.4, "within 180 days"
    if delta <= 365:
        return 0.22, "within 365 days"
    return 0.08, "older than 365 days"


def match_scope(
    *,
    subject_tree_id: UUID | None,
    subject_row_id: UUID | None,
    subject_parcel_id: UUID | None,
    item_tree_id: UUID | None,
    item_row_id: UUID | None,
    item_parcel_id: UUID | None,
    extra_row_ids: list[str] | None = None,
    recorded_scope: ContextScope | None = None,
) -> tuple[ContextScope, float, str]:
    extras = {str(item) for item in (extra_row_ids or [])}
    if subject_tree_id and item_tree_id == subject_tree_id:
        return ContextScope.TREE, SCOPE_SCORE[ContextScope.TREE], "same tree"
    if subject_row_id and (item_row_id == subject_row_id or str(subject_row_id) in extras):
        return ContextScope.ROW, SCOPE_SCORE[ContextScope.ROW], "same row"
    if subject_parcel_id and item_parcel_id == subject_parcel_id:
        return ContextScope.PARCEL, SCOPE_SCORE[ContextScope.PARCEL], "same parcel"
    if recorded_scope is not None:
        return recorded_scope, SCOPE_SCORE.get(recorded_scope, 0.1), f"recorded scope {recorded_scope.value}"
    return ContextScope.FARM, SCOPE_SCORE[ContextScope.FARM], "same farm"


def activity_type_relevance(
    request_type: ContextRequestType,
    slug: str | None,
    *,
    focus_slug: str | None = None,
) -> tuple[float, str]:
    key = (slug or "other").lower()
    if request_type == ContextRequestType.ACTIVITY_ANALYSIS and focus_slug:
        if key == focus_slug.lower():
            return 1.0, f"same activity type ({key})"
        return 0.55, f"related activity type ({key})"
    table = (
        PHOTO_PROBLEM_ACTIVITY_TYPE
        if request_type in {ContextRequestType.PHOTO_ANALYSIS, ContextRequestType.PROBLEM_ANALYSIS}
        else PARCEL_SEASON_ACTIVITY_TYPE
    )
    score = table.get(key, 0.4)
    if score >= 0.75:
        return score, f"activity type relevant ({key})"
    return score, f"activity type {key}"


def combine_score(
    request_type: ContextRequestType,
    scope_score: float,
    temporal_score: float,
    type_score: float,
) -> float:
    w_scope, w_time, w_type = WEIGHTS[request_type]
    return clamp_score(w_scope * scope_score + w_time * temporal_score + w_type * type_score)


def photo_type_relevance(*, is_current: bool, entity_type: str) -> tuple[float, str]:
    if is_current:
        return 1.0, "current photo"
    if entity_type == "tree":
        return 0.9, "tree photo"
    if entity_type in {"row", "observation", "disease_case"}:
        return 0.75, f"{entity_type} photo"
    if entity_type == "parcel":
        return 0.55, "parcel photo"
    if entity_type == "activity":
        return 0.6, "activity photo"
    return 0.4, f"{entity_type} photo"
