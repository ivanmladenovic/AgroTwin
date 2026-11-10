"""Intelligence context: zone anomalies, thresholds, alert lifecycle helpers."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.core.config import get_settings
from app.intelligence.satellite_context import sat_observation_summary, serialize_zone_anomalies
from app.intelligence.schema import ParcelIntelligenceAIResult
from app.models.enums import ParcelAlertSeverity, ParcelAlertStatus, SatelliteAnomalyKind
from app.models.intelligence import ParcelAlert
from app.satellite.anomalies import ZoneSnapshot, detect_anomalies
from app.services.intelligence import (
    _evidence_from_result,
    _evidence_materially_changed,
)


class ThresholdConfigurationTests(TestCase):
    """Zone anomaly thresholds are relative NDVI fractions — not absolute index cutoffs."""

    def test_thresholds_are_independent_config_fields(self) -> None:
        settings = get_settings()
        self.assertTrue(hasattr(settings, "satellite_anomaly_below_mean_fraction"))
        self.assertTrue(hasattr(settings, "satellite_anomaly_sudden_decline_fraction"))
        self.assertNotEqual(
            settings.satellite_anomaly_below_mean_fraction,
            settings.satellite_anomaly_sudden_decline_fraction,
        )

    def test_ndvi_relative_thresholds_drive_detection(self) -> None:
        # 15% below mean of 0.60 → trigger at <= 0.51
        findings = detect_anomalies(
            parcel_ndvi_mean=Decimal("0.60"),
            current_zones=[ZoneSnapshot(zone_key="r0c0", ndvi=Decimal("0.50"), ndre=Decimal("0.20"))],
            previous_zones=None,
            below_mean_fraction=0.15,
            sudden_decline_fraction=0.20,
        )
        self.assertTrue(any(item.kind == SatelliteAnomalyKind.BELOW_PARCEL_MEAN for item in findings))
        self.assertTrue(all(item.index_name == "ndvi" for item in findings))

    def test_ndre_ndwi_not_used_by_zone_detector(self) -> None:
        # Extreme NDRE/NDWI with healthy NDVI must not create findings.
        findings = detect_anomalies(
            parcel_ndvi_mean=Decimal("0.60"),
            current_zones=[
                ZoneSnapshot(
                    zone_key="r0c0",
                    ndvi=Decimal("0.60"),
                    ndre=Decimal("0.01"),
                    ndwi=Decimal("-0.40"),
                )
            ],
            previous_zones=None,
            below_mean_fraction=0.15,
            sudden_decline_fraction=0.20,
        )
        self.assertEqual(findings, [])


class ZoneAnomalySerializationTests(TestCase):
    def test_serialize_zone_anomalies_includes_details(self) -> None:
        observation = SimpleNamespace(
            acquisition_date=__import__("datetime").date(2026, 10, 4),
            cloud_cover=Decimal("12.5"),
            ndvi_mean=Decimal("0.55"),
            ndvi_min=Decimal("0.30"),
            ndvi_max=Decimal("0.70"),
            ndre_mean=Decimal("0.30"),
            ndwi_mean=Decimal("0.05"),
            anomaly_count=1,
            processing_status=SimpleNamespace(value="completed"),
            zones=[
                SimpleNamespace(zone_key="r0c3", ndvi=Decimal("0.40"), ndre=None, ndwi=None),
            ],
            anomalies=[
                SimpleNamespace(
                    zone_key="r0c3",
                    kind=SatelliteAnomalyKind.BELOW_PARCEL_MEAN,
                    index_name="ndvi",
                    severity=Decimal("0.1800"),
                    message="Moguća anomalija",
                    details={
                        "zone_ndvi": "0.40",
                        "parcel_ndvi_mean": "0.55",
                        "relative_deviation": -0.2727,
                    },
                )
            ],
        )
        rows = serialize_zone_anomalies(observation)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["zone_key"], "r0c3")
        self.assertEqual(rows[0]["kind"], "below_parcel_mean")
        self.assertEqual(rows[0]["index_name"], "ndvi")
        self.assertEqual(rows[0]["zone_value"], "0.40")
        self.assertEqual(rows[0]["parcel_reference_value"], "0.55")
        self.assertEqual(rows[0]["comparison_available"], "vs_parcel_mean")

    def test_missing_previous_observation_marked(self) -> None:
        observation = SimpleNamespace(
            acquisition_date=__import__("datetime").date(2026, 10, 4),
            cloud_cover=None,
            ndvi_mean=Decimal("0.55"),
            ndvi_min=None,
            ndvi_max=None,
            ndre_mean=None,
            ndwi_mean=None,
            anomaly_count=1,
            processing_status=SimpleNamespace(value="completed"),
            zones=[],
            anomalies=[
                SimpleNamespace(
                    zone_key="r1c1",
                    kind=SatelliteAnomalyKind.SUDDEN_DECLINE,
                    index_name="ndvi",
                    severity=Decimal("0.25"),
                    message="pad",
                    details={"zone_ndvi": "0.40"},  # no previous_ndvi
                )
            ],
        )
        rows = serialize_zone_anomalies(observation)
        self.assertEqual(rows[0]["comparison_available"], "insufficient_history")
        self.assertIsNone(rows[0]["previous_value"])

    def test_sat_summary_without_observation(self) -> None:
        self.assertIsNone(sat_observation_summary(None))


class SchemaAndAlertLifecycleTests(TestCase):
    def test_schema_accepts_zone_fields(self) -> None:
        payload = ParcelIntelligenceAIResult.model_validate(
            {
                "status": "WARNING",
                "title": "Test",
                "summary": "Summary",
                "observed_facts": ["zona r0c3 ispod proseka"],
                "possible_causes": ["mogući vodni stres"],
                "recommended_actions": ["obići parcelu"],
                "confidence": 0.6,
                "should_notify": True,
                "issue_key": "ndvi_zone_anomaly",
                "zone_keys": ["r0c3", "r2c0"],
                "affected_indices": ["NDVI", "bogus"],
                "observation_date": "2026-10-04",
                "data_quality_notes": ["cloud_cover elevated"],
            }
        )
        self.assertEqual(payload.zone_keys, ["r0c3", "r2c0"])
        self.assertEqual(payload.affected_indices, ["ndvi"])
        self.assertEqual(payload.observation_date, "2026-10-04")

    def test_ok_result_does_not_imply_auto_resolve_helper(self) -> None:
        # Documented contract: callers must not resolve all alerts on OK.
        result = ParcelIntelligenceAIResult.model_validate(
            {
                "status": "OK",
                "title": "OK",
                "summary": "Nema problema",
                "confidence": 0.9,
                "should_notify": False,
            }
        )
        self.assertEqual(result.status, "OK")
        self.assertGreaterEqual(result.confidence, 0.5)

    def test_evidence_material_change_detects_zone_update(self) -> None:
        alert = ParcelAlert(
            id=uuid4(),
            parcel_id=uuid4(),
            severity=ParcelAlertSeverity.WARNING,
            status=ParcelAlertStatus.OPEN,
            issue_key="ndvi_zone_anomaly",
            title="Old",
            summary="Old summary",
            observed_facts=["a"],
            possible_causes=["x"],
            recommended_actions=["y"],
            source_events=["satellite_anomaly"],
            confidence=Decimal("0.5"),
            evidence={"zone_keys": ["r0c0"], "affected_indices": ["ndvi"], "observation_date": "2026-09-01"},
        )
        result = ParcelIntelligenceAIResult.model_validate(
            {
                "status": "WARNING",
                "title": "Old",
                "summary": "Old summary",
                "observed_facts": ["a"],
                "possible_causes": ["x"],
                "recommended_actions": ["y"],
                "confidence": 0.5,
                "issue_key": "ndvi_zone_anomaly",
                "zone_keys": ["r0c0", "r1c1"],
                "affected_indices": ["ndvi"],
                "observation_date": "2026-10-04",
            }
        )
        evidence = _evidence_from_result(result)
        self.assertTrue(_evidence_materially_changed(alert, result, evidence))
