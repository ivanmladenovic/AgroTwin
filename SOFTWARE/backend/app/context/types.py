"""Shared enums and constants for the AgroTwin Context Engine."""

from __future__ import annotations

from enum import Enum

CONTEXT_VERSION = "1.0"

GLOBAL_KNOWLEDGE_SCOPE = "GLOBAL_KNOWLEDGE"


class ContextRequestType(str, Enum):
    PHOTO_ANALYSIS = "PHOTO_ANALYSIS"
    PROBLEM_ANALYSIS = "PROBLEM_ANALYSIS"
    PARCEL_ANALYSIS = "PARCEL_ANALYSIS"
    SEASON_ANALYSIS = "SEASON_ANALYSIS"
    ACTIVITY_ANALYSIS = "ACTIVITY_ANALYSIS"


class SubjectType(str, Enum):
    FARM = "FARM"
    PARCEL = "PARCEL"
    ROW = "ROW"
    TREE = "TREE"


class ContextScope(str, Enum):
    FARM = "FARM"
    PARCEL = "PARCEL"
    ROW = "ROW"
    TREE = "TREE"
    GLOBAL = "GLOBAL"
    GLOBAL_KNOWLEDGE = "GLOBAL_KNOWLEDGE"


class DataQualityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"
    EXCLUDED = "EXCLUDED"


class TemporalRelation(str, Enum):
    BEFORE_EVENT = "before_event"
    AFTER_EVENT = "after_event"
    DURING_PERIOD = "during_period"
    CURRENT = "current"
    HISTORICAL = "historical"


class WarningType(str, Enum):
    MISSING_DATA = "MISSING_DATA"
    STALE_DATA = "STALE_DATA"
    PARTIAL_DATA = "PARTIAL_DATA"
    SOURCE_ERROR = "SOURCE_ERROR"
    LIMITED_HISTORY = "LIMITED_HISTORY"
    EXCLUDED_BY_PROFILE = "EXCLUDED_BY_PROFILE"
    HIERARCHY_MISMATCH = "HIERARCHY_MISMATCH"


class SourceType(str, Enum):
    USER_RECORD = "user_record"
    MODELED_ESTIMATE = "modeled_estimate"
    EXTERNAL_WEATHER_DATA = "external_weather_data"
    PREVIOUS_AI_ANALYSIS = "previous_ai_analysis"
    DERIVED_SUMMARY = "derived_summary"
