"""Deterministic profile configuration for Context Engine V1.

Profiles choose *what* to collect. Ranking chooses *which* records to keep.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.context.types import ContextRequestType


@dataclass(frozen=True)
class ContextBudget:
    max_activities: int = 30
    max_photos: int = 20
    max_ai_analyses: int = 10
    max_weather_records: int = 14
    max_harvest_events: int = 20
    max_problems: int = 10
    max_excluded_debug: int = 40


@dataclass(frozen=True)
class ContextProfile:
    request_type: ContextRequestType
    recent_activity_days: int
    older_activity_days: int | None
    weather_days: int
    include_soil: bool
    include_weather: bool
    include_activities: bool
    include_photos: bool
    include_ai: bool
    include_costs: bool
    include_harvest: bool
    include_problems: bool
    summarize_activities: bool
    summarize_harvest: bool
    summarize_costs: bool
    summarize_photos: bool
    budget: ContextBudget


_PHOTO = ContextProfile(
    request_type=ContextRequestType.PHOTO_ANALYSIS,
    recent_activity_days=90,
    older_activity_days=180,
    weather_days=7,
    include_soil=True,
    include_weather=True,
    include_activities=True,
    include_photos=True,
    include_ai=True,
    include_costs=False,
    include_harvest=False,
    include_problems=True,
    summarize_activities=False,
    summarize_harvest=False,
    summarize_costs=False,
    summarize_photos=False,
    budget=ContextBudget(
        max_activities=20,
        max_photos=12,
        max_ai_analyses=8,
        max_weather_records=7,
        max_harvest_events=0,
        max_problems=8,
    ),
)

_PROBLEM = ContextProfile(
    request_type=ContextRequestType.PROBLEM_ANALYSIS,
    recent_activity_days=90,
    older_activity_days=365,
    weather_days=30,
    include_soil=True,
    include_weather=True,
    include_activities=True,
    include_photos=True,
    include_ai=True,
    include_costs=False,
    include_harvest=True,
    include_problems=True,
    summarize_activities=False,
    summarize_harvest=True,
    summarize_costs=False,
    summarize_photos=False,
    budget=ContextBudget(
        max_activities=25,
        max_photos=12,
        max_ai_analyses=10,
        max_weather_records=14,
        max_harvest_events=8,
        max_problems=10,
    ),
)

_PARCEL = ContextProfile(
    request_type=ContextRequestType.PARCEL_ANALYSIS,
    recent_activity_days=0,
    older_activity_days=None,
    weather_days=7,
    include_soil=True,
    include_weather=True,
    include_activities=True,
    include_photos=True,
    include_ai=True,
    include_costs=True,
    include_harvest=True,
    include_problems=True,
    summarize_activities=True,
    summarize_harvest=True,
    summarize_costs=True,
    summarize_photos=True,
    budget=ContextBudget(
        max_activities=20,
        max_photos=8,
        max_ai_analyses=6,
        max_weather_records=7,
        max_harvest_events=12,
        max_problems=10,
    ),
)

_SEASON = ContextProfile(
    request_type=ContextRequestType.SEASON_ANALYSIS,
    recent_activity_days=0,
    older_activity_days=None,
    weather_days=7,
    include_soil=True,
    include_weather=True,
    include_activities=True,
    include_photos=True,
    include_ai=True,
    include_costs=True,
    include_harvest=True,
    include_problems=True,
    summarize_activities=True,
    summarize_harvest=True,
    summarize_costs=True,
    summarize_photos=True,
    budget=ContextBudget(
        max_activities=30,
        max_photos=8,
        max_ai_analyses=8,
        max_weather_records=14,
        max_harvest_events=20,
        max_problems=10,
    ),
)

_ACTIVITY = ContextProfile(
    request_type=ContextRequestType.ACTIVITY_ANALYSIS,
    recent_activity_days=90,
    older_activity_days=180,
    weather_days=7,
    include_soil=True,
    include_weather=True,
    include_activities=True,
    include_photos=True,
    include_ai=True,
    include_costs=True,
    include_harvest=False,
    include_problems=True,
    summarize_activities=False,
    summarize_harvest=False,
    summarize_costs=False,
    summarize_photos=False,
    budget=ContextBudget(
        max_activities=15,
        max_photos=8,
        max_ai_analyses=5,
        max_weather_records=7,
        max_harvest_events=0,
        max_problems=6,
    ),
)

PROFILES: dict[ContextRequestType, ContextProfile] = {
    ContextRequestType.PHOTO_ANALYSIS: _PHOTO,
    ContextRequestType.PROBLEM_ANALYSIS: _PROBLEM,
    ContextRequestType.PARCEL_ANALYSIS: _PARCEL,
    ContextRequestType.SEASON_ANALYSIS: _SEASON,
    ContextRequestType.ACTIVITY_ANALYSIS: _ACTIVITY,
}


def get_profile(request_type: ContextRequestType) -> ContextProfile:
    return PROFILES[request_type]
