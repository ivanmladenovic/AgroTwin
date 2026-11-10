from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from pydantic import ValidationError

from app.intelligence.change_detection import detect_meaningful_changes
from app.intelligence.schema import ParcelIntelligenceAIResult
from app.models.enums import ParcelAlertSeverity, ParcelAlertStatus
from app.models.intelligence import ParcelAlert
from app.services.intelligence import _parse_json_object


class ChangeDetectionTests(TestCase):
    def test_no_change_skips_ai(self) -> None:
        result = detect_meaningful_changes(
            force=False,
            trigger_kinds=["scheduled"],
            latest_satellite={"ndvi_mean": "0.55"},
            previous_satellite={"ndvi_mean": "0.54"},
            anomaly_count=0,
            recent_activity_slugs=[],
            yield_deviation_percent=None,
            open_alert_count=0,
            last_analysis_at=datetime.now(timezone.utc) - timedelta(hours=2),
            min_interval_hours=24,
            ndvi_change_threshold=0.08,
        )
        self.assertFalse(result.should_call_ai)
        self.assertEqual(result.reason, "min_interval_not_elapsed")

    def test_satellite_anomaly_triggers_ai(self) -> None:
        result = detect_meaningful_changes(
            force=False,
            trigger_kinds=["satellite_anomaly"],
            latest_satellite={"ndvi_mean": "0.40"},
            previous_satellite={"ndvi_mean": "0.55"},
            anomaly_count=3,
            recent_activity_slugs=[],
            yield_deviation_percent=None,
            open_alert_count=0,
            last_analysis_at=None,
            min_interval_hours=24,
        )
        self.assertTrue(result.should_call_ai)
        codes = {s.code for s in result.signals}
        self.assertIn("satellite_anomaly", codes)

    def test_manual_force(self) -> None:
        result = detect_meaningful_changes(
            force=True,
            trigger_kinds=[],
            latest_satellite=None,
            previous_satellite=None,
            anomaly_count=0,
            recent_activity_slugs=[],
            yield_deviation_percent=None,
            open_alert_count=0,
            last_analysis_at=datetime.now(timezone.utc),
            min_interval_hours=24,
        )
        self.assertTrue(result.should_call_ai)


class SchemaValidationTests(TestCase):
    def test_valid_payload(self) -> None:
        payload = ParcelIntelligenceAIResult.model_validate(
            {
                "status": "WARNING",
                "title": "Test",
                "summary": "Summary",
                "observed_facts": ["a"],
                "possible_causes": ["mogući vodni stres"],
                "recommended_actions": ["obići parcelu"],
                "confidence": 0.6,
                "should_notify": True,
                "issue_key": "ndvi_decline",
            }
        )
        self.assertEqual(payload.status, "WARNING")

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ParcelIntelligenceAIResult.model_validate(
                {
                    "status": "CONFIRMED_DISEASE",
                    "title": "x",
                    "summary": "y",
                    "confidence": 0.1,
                }
            )

    def test_parse_json_object_rejects_array(self) -> None:
        with self.assertRaises(ValueError):
            _parse_json_object("[1,2,3]")


class DedupEscalationLogicTests(TestCase):
    def test_severity_rank_escalation(self) -> None:
        from app.services.intelligence import _SEVERITY_RANK

        self.assertGreater(
            _SEVERITY_RANK[ParcelAlertSeverity.CRITICAL],
            _SEVERITY_RANK[ParcelAlertSeverity.WARNING],
        )
        self.assertGreater(
            _SEVERITY_RANK[ParcelAlertSeverity.WARNING],
            _SEVERITY_RANK[ParcelAlertSeverity.INFO],
        )

    def test_existing_alert_fields(self) -> None:
        alert = ParcelAlert(
            id=uuid4(),
            parcel_id=uuid4(),
            severity=ParcelAlertSeverity.INFO,
            status=ParcelAlertStatus.OPEN,
            issue_key="ndvi_decline",
            title="Old",
            summary="Old summary",
            observed_facts=["a"],
            possible_causes=[],
            recommended_actions=[],
            source_events=["satellite_observation"],
            confidence=Decimal("0.4"),
        )
        self.assertEqual(alert.status, ParcelAlertStatus.OPEN)
        alert.status = ParcelAlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        self.assertEqual(alert.status, ParcelAlertStatus.RESOLVED)
