from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from uuid import uuid4
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.context.profiles import get_profile
from app.context.ranking import (
    activity_type_relevance,
    combine_score,
    match_scope,
    temporal_relevance,
)
from app.context.soil_map import snapshot_is_stale, surface_properties
from app.context.temporal import temporal_relation
from app.context.types import ContextRequestType, ContextScope, TemporalRelation
from app.context.weather_agg import WeatherDay, aggregate_weather, parse_weather_days


class RankingTests(TestCase):
    def test_same_tree_recent_outranks_same_parcel_old(self) -> None:
        event = date(2026, 9, 10)
        tree_id = uuid4()
        parcel_id = uuid4()
        tree_scope, tree_score, _ = match_scope(
            subject_tree_id=tree_id,
            subject_row_id=uuid4(),
            subject_parcel_id=parcel_id,
            item_tree_id=tree_id,
            item_row_id=None,
            item_parcel_id=parcel_id,
        )
        parcel_scope, parcel_score, _ = match_scope(
            subject_tree_id=tree_id,
            subject_row_id=uuid4(),
            subject_parcel_id=parcel_id,
            item_tree_id=None,
            item_row_id=None,
            item_parcel_id=parcel_id,
        )
        self.assertEqual(tree_scope, ContextScope.TREE)
        self.assertEqual(parcel_scope, ContextScope.PARCEL)
        recent, _ = temporal_relevance(date(2026, 8, 20), event)
        old, _ = temporal_relevance(date(2025, 3, 1), event)
        type_score, _ = activity_type_relevance(ContextRequestType.PHOTO_ANALYSIS, "spraying")
        tree_recent = combine_score(ContextRequestType.PHOTO_ANALYSIS, tree_score, recent, type_score)
        parcel_old = combine_score(ContextRequestType.PHOTO_ANALYSIS, parcel_score, old, type_score)
        self.assertGreater(tree_recent, parcel_old)

    def test_scope_order_tree_row_parcel(self) -> None:
        tree_id, row_id, parcel_id = uuid4(), uuid4(), uuid4()
        _, tree_score, tree_reason = match_scope(
            subject_tree_id=tree_id,
            subject_row_id=row_id,
            subject_parcel_id=parcel_id,
            item_tree_id=tree_id,
            item_row_id=row_id,
            item_parcel_id=parcel_id,
        )
        _, row_score, row_reason = match_scope(
            subject_tree_id=tree_id,
            subject_row_id=row_id,
            subject_parcel_id=parcel_id,
            item_tree_id=None,
            item_row_id=row_id,
            item_parcel_id=parcel_id,
        )
        _, parcel_score, _ = match_scope(
            subject_tree_id=tree_id,
            subject_row_id=row_id,
            subject_parcel_id=parcel_id,
            item_tree_id=None,
            item_row_id=None,
            item_parcel_id=parcel_id,
        )
        self.assertGreater(tree_score, row_score)
        self.assertGreater(row_score, parcel_score)
        self.assertEqual(tree_reason, "same tree")
        self.assertEqual(row_reason, "same row")

    def test_extra_row_ids_count_as_same_row(self) -> None:
        row_id = uuid4()
        scope, _, reason = match_scope(
            subject_tree_id=None,
            subject_row_id=row_id,
            subject_parcel_id=uuid4(),
            item_tree_id=None,
            item_row_id=None,
            item_parcel_id=uuid4(),
            extra_row_ids=[str(row_id)],
        )
        self.assertEqual(scope, ContextScope.ROW)
        self.assertEqual(reason, "same row")

    def test_spraying_is_relevant_for_photo_analysis(self) -> None:
        high, reason = activity_type_relevance(ContextRequestType.PHOTO_ANALYSIS, "spraying")
        low, _ = activity_type_relevance(ContextRequestType.PHOTO_ANALYSIS, "harvesting")
        self.assertGreater(high, low)
        self.assertIn("spraying", reason)


class TemporalTests(TestCase):
    def test_before_after_and_current(self) -> None:
        event = date(2026, 9, 10)
        self.assertEqual(temporal_relation(date(2026, 9, 5), event), TemporalRelation.BEFORE_EVENT)
        self.assertEqual(temporal_relation(date(2026, 9, 15), event), TemporalRelation.AFTER_EVENT)
        self.assertEqual(temporal_relation(date(2026, 9, 10), event), TemporalRelation.CURRENT)

    def test_during_period(self) -> None:
        event = date(2026, 9, 10)
        self.assertEqual(
            temporal_relation(date(2026, 6, 1), event, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)),
            TemporalRelation.DURING_PERIOD,
        )


class ProfileTests(TestCase):
    def test_photo_excludes_costs_and_harvest(self) -> None:
        profile = get_profile(ContextRequestType.PHOTO_ANALYSIS)
        self.assertFalse(profile.include_costs)
        self.assertFalse(profile.include_harvest)
        self.assertEqual(profile.recent_activity_days, 90)
        self.assertEqual(profile.older_activity_days, 180)

    def test_problem_allows_older_year_window(self) -> None:
        profile = get_profile(ContextRequestType.PROBLEM_ANALYSIS)
        self.assertEqual(profile.older_activity_days, 365)
        self.assertTrue(profile.include_harvest)

    def test_season_and_parcel_include_costs(self) -> None:
        self.assertTrue(get_profile(ContextRequestType.PARCEL_ANALYSIS).include_costs)
        self.assertTrue(get_profile(ContextRequestType.SEASON_ANALYSIS).include_costs)
        self.assertTrue(get_profile(ContextRequestType.ACTIVITY_ANALYSIS).include_costs)


class WeatherAggregateTests(TestCase):
    def test_aggregates_without_agronomic_interpretation(self) -> None:
        days = [
            WeatherDay(date(2026, 9, 8), -2.1, 4.0, 0.0),
            WeatherDay(date(2026, 9, 9), 12.0, 31.5, 3.2),
            WeatherDay(date(2026, 9, 10), None, None, None),
        ]
        result = aggregate_weather(days)
        self.assertEqual(result.minimum_temperature, -2.1)
        self.assertEqual(result.maximum_temperature, 31.5)
        self.assertEqual(result.frost_days, 1)
        self.assertEqual(result.hot_days, 1)
        self.assertEqual(result.rainy_days, 1)
        self.assertEqual(result.record_count, 3)
        self.assertIsNotNone(result.average_temperature)

    def test_missing_temperatures_are_not_zero(self) -> None:
        result = aggregate_weather([WeatherDay(date(2026, 9, 10), None, None, None)])
        self.assertIsNone(result.minimum_temperature)
        self.assertIsNone(result.maximum_temperature)
        self.assertIsNone(result.average_temperature)
        self.assertIsNone(result.precipitation)

    def test_parse_ignores_malformed_rows(self) -> None:
        days = parse_weather_days(
            [
                {"date": "2026-09-10", "min_temperature": 8, "max_temperature": 18, "precipitation": 0},
                {"date": "bad"},
                {"min_temperature": 1},
            ]
        )
        self.assertEqual(len(days), 1)


class SoilMapTests(TestCase):
    def test_stale_snapshot(self) -> None:
        now = datetime(2026, 9, 22, tzinfo=timezone.utc)

        class Snap:
            expires_at = now - timedelta(days=10)

        self.assertTrue(snapshot_is_stale(Snap(), now))  # type: ignore[arg-type]

        class Fresh:
            expires_at = now + timedelta(days=1)

        self.assertFalse(snapshot_is_stale(Fresh(), now))  # type: ignore[arg-type]

    def test_missing_properties_stay_none(self) -> None:
        mapped = surface_properties({"ph": {"0-5cm": {"value": 6.4, "unit": ""}}})
        self.assertEqual(mapped["ph"]["value"], 6.4)
        self.assertIsNone(mapped["clay"]["value"])
        self.assertFalse(mapped["clay"]["available"])
        self.assertNotEqual(mapped["clay"]["value"], 0)


class EngineHelperTests(TestCase):
    def test_budget_keeps_highest_scoring_records(self) -> None:
        from app.context.engine import _apply_budgets
        from app.context.providers.base import ProviderResult, RankedItem
        from app.context.types import DataQualityStatus

        profile = get_profile(ContextRequestType.PHOTO_ANALYSIS)
        items = [
            RankedItem(
                kind="activity",
                id=str(index),
                payload=None,
                relevance_score=1 - index * 0.01,
                reasons=["test"],
            )
            for index in range(40)
        ]
        results = {
            "activities": ProviderResult(
                "activities",
                "user_record",
                DataQualityStatus.AVAILABLE,
                items=items,
                collected=40,
            )
        }
        selected, excluded = _apply_budgets(results, profile)
        self.assertEqual(len(selected["activities"]), profile.budget.max_activities)
        self.assertEqual(len(excluded["activities"]), 40 - profile.budget.max_activities)
        self.assertGreater(selected["activities"][0].relevance_score, excluded["activities"][0].relevance_score)

    def test_soil_error_message_does_not_claim_lab_data(self) -> None:
        from app.context.engine import _provider_error_message

        message = _provider_error_message("soil")
        self.assertIn("SoilGrids", message)
        self.assertNotIn("laborator", message.lower())
