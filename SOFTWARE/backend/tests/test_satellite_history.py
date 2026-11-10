"""Satellite observation history: series, nulls, duplicates, recurrence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.models.enums import SatelliteAnomalyKind
from app.satellite.history import build_satellite_history


def _obs(
    *,
    parcel_id,
    product_id: str,
    acquired: date,
    processed: datetime | None = None,
    ndvi=None,
    ndre=None,
    ndwi=None,
    cloud=None,
    anomalies=None,
    zones=None,
    metadata=None,
):
    return SimpleNamespace(
        id=uuid4(),
        parcel_id=parcel_id,
        provider="fake",
        product_id=product_id,
        acquisition_date=acquired,
        processed_at=processed,
        created_at=processed,
        cloud_cover=cloud,
        ndvi_mean=ndvi,
        ndre_mean=ndre,
        ndwi_mean=ndwi,
        anomaly_count=len(anomalies or []),
        source_metadata=metadata or {},
        zones=zones or [],
        anomalies=anomalies or [],
    )


def _zone(key: str, geometry: dict | None):
    return SimpleNamespace(zone_key=key, geometry=geometry, ndvi=None, ndre=None, ndwi=None)


def _anomaly(key: str, kind=SatelliteAnomalyKind.BELOW_PARCEL_MEAN):
    return SimpleNamespace(zone_key=key, kind=kind, index_name="ndvi", severity=Decimal("0.2"))


CELL = {
    "type": "Polygon",
    "coordinates": [[[20.0, 44.0], [20.01, 44.0], [20.01, 44.01], [20.0, 44.01], [20.0, 44.0]]],
}


class SatelliteHistoryTests(TestCase):
    def test_empty_history(self) -> None:
        parcel_id = uuid4()
        result = build_satellite_history([], parcel_id=parcel_id)
        self.assertEqual(result["point_count"], 0)
        self.assertIsNone(result["earliest_acquisition_date"])
        self.assertEqual(result["repeated_anomalies"], [])
        self.assertTrue(any("Nema sačuvanih" in note for note in result["notes"]))

    def test_single_observation_has_no_delta(self) -> None:
        parcel_id = uuid4()
        obs = _obs(
            parcel_id=parcel_id,
            product_id="S2-1",
            acquired=date(2026, 6, 1),
            processed=datetime(2026, 6, 2, tzinfo=timezone.utc),
            ndvi=Decimal("0.55"),
            ndre=None,
            ndwi=Decimal("0.10"),
            cloud=Decimal("8"),
        )
        result = build_satellite_history([obs], parcel_id=parcel_id)
        point = result["points"][0]
        self.assertEqual(point["ndvi_mean"], Decimal("0.55"))
        self.assertIsNone(point["ndre_mean"])
        self.assertIsNone(point["ndvi_delta"])
        self.assertIsNone(point["ndre_delta"])
        self.assertNotEqual(point["ndwi_mean"], 0)
        self.assertEqual(point["acquisition_date"], date(2026, 6, 1))
        self.assertEqual(point["processed_at"].date(), date(2026, 6, 2))

    def test_multiple_observations_absolute_delta_skips_null(self) -> None:
        parcel_id = uuid4()
        first = _obs(
            parcel_id=parcel_id,
            product_id="S2-1",
            acquired=date(2026, 5, 1),
            ndvi=Decimal("0.50"),
            ndre=Decimal("0.20"),
            cloud=Decimal("5"),
        )
        gap = _obs(
            parcel_id=parcel_id,
            product_id="S2-2",
            acquired=date(2026, 6, 1),
            ndvi=None,
            ndre=Decimal("0.25"),
            cloud=Decimal("10"),
        )
        third = _obs(
            parcel_id=parcel_id,
            product_id="S2-3",
            acquired=date(2026, 7, 1),
            ndvi=Decimal("0.42"),
            ndre=Decimal("0.22"),
            cloud=Decimal("4"),
        )
        result = build_satellite_history([third, first, gap], parcel_id=parcel_id)
        self.assertEqual([p["product_id"] for p in result["points"]], ["S2-1", "S2-2", "S2-3"])
        self.assertIsNone(result["points"][1]["ndvi_mean"])
        self.assertIsNone(result["points"][1]["ndvi_delta"])
        # NDVI delta uses the previous observation that actually has NDVI (May), not the null June row.
        self.assertEqual(result["points"][2]["ndvi_delta"], Decimal("-0.0800"))
        self.assertEqual(result["points"][1]["ndre_delta"], Decimal("0.0500"))
        self.assertTrue(result["points"][2]["ndvi_comparison_reliable"])

    def test_duplicate_product_keeps_later_processing(self) -> None:
        parcel_id = uuid4()
        older = _obs(
            parcel_id=parcel_id,
            product_id="S2-same",
            acquired=date(2026, 8, 1),
            processed=datetime(2026, 8, 2, tzinfo=timezone.utc),
            ndvi=Decimal("0.40"),
        )
        newer = _obs(
            parcel_id=parcel_id,
            product_id="S2-same",
            acquired=date(2026, 8, 1),
            processed=datetime(2026, 8, 3, tzinfo=timezone.utc),
            ndvi=Decimal("0.44"),
        )
        result = build_satellite_history([older, newer], parcel_id=parcel_id)
        self.assertEqual(result["point_count"], 1)
        self.assertEqual(result["points"][0]["ndvi_mean"], Decimal("0.44"))

    def test_other_parcel_is_excluded(self) -> None:
        parcel_id = uuid4()
        foreign = _obs(
            parcel_id=uuid4(),
            product_id="S2-other",
            acquired=date(2026, 8, 1),
            ndvi=Decimal("0.9"),
        )
        own = _obs(
            parcel_id=parcel_id,
            product_id="S2-own",
            acquired=date(2026, 8, 2),
            ndvi=Decimal("0.3"),
        )
        result = build_satellite_history([foreign, own], parcel_id=parcel_id)
        self.assertEqual(result["point_count"], 1)
        self.assertEqual(result["points"][0]["product_id"], "S2-own")

    def test_date_filter_and_nan_cloud(self) -> None:
        parcel_id = uuid4()
        rows = [
            _obs(parcel_id=parcel_id, product_id="a", acquired=date(2026, 1, 1), ndvi=Decimal("0.2"), cloud=Decimal("40")),
            _obs(parcel_id=parcel_id, product_id="b", acquired=date(2026, 6, 1), ndvi=Decimal("0.3"), cloud=None),
            _obs(parcel_id=parcel_id, product_id="c", acquired=date(2026, 9, 1), ndvi=Decimal("0.4"), cloud=Decimal("5")),
        ]
        result = build_satellite_history(
            rows,
            parcel_id=parcel_id,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 8, 1),
        )
        self.assertEqual(result["point_count"], 1)
        self.assertEqual(result["points"][0]["product_id"], "b")
        self.assertEqual(result["points"][0]["quality"], "unknown")
        self.assertEqual(result["earliest_acquisition_date"], date(2026, 1, 1))
        self.assertEqual(rows[0].cloud_cover, Decimal("40"))

    def test_elevated_cloud_delta_is_not_treated_as_reliable(self) -> None:
        parcel_id = uuid4()
        clear = _obs(
            parcel_id=parcel_id,
            product_id="clear",
            acquired=date(2026, 5, 1),
            ndvi=Decimal("0.60"),
            cloud=Decimal("5"),
        )
        cloudy = _obs(
            parcel_id=parcel_id,
            product_id="cloudy",
            acquired=date(2026, 6, 1),
            ndvi=Decimal("0.20"),
            cloud=Decimal("35"),
        )
        result = build_satellite_history([clear, cloudy], parcel_id=parcel_id)
        point = result["points"][1]
        self.assertEqual(point["quality"], "elevated_cloud")
        self.assertEqual(point["ndvi_delta"], Decimal("-0.4000"))
        self.assertFalse(point["ndvi_comparison_reliable"])
        self.assertEqual(result["repeated_anomalies"], [])

    def test_repeated_zone_without_geometry_is_potential(self) -> None:
        parcel_id = uuid4()
        anomaly = _anomaly("r0c0")
        first = _obs(
            parcel_id=parcel_id,
            product_id="a",
            acquired=date(2026, 5, 1),
            ndvi=Decimal("0.4"),
            anomalies=[anomaly],
            zones=[_zone("r0c0", None)],
        )
        second = _obs(
            parcel_id=parcel_id,
            product_id="b",
            acquired=date(2026, 6, 1),
            ndvi=Decimal("0.4"),
            anomalies=[_anomaly("r0c0")],
            zones=[_zone("r0c0", None)],
        )
        result = build_satellite_history([first, second], parcel_id=parcel_id)
        self.assertEqual(len(result["repeated_anomalies"]), 1)
        row = result["repeated_anomalies"][0]
        self.assertEqual(row["relation"], "potentially_related")
        self.assertEqual(row["occurrence_count"], 2)
        self.assertNotIn("same_grid_cell", row["relation"])

    def test_repeated_zone_with_matching_geometry(self) -> None:
        parcel_id = uuid4()
        first = _obs(
            parcel_id=parcel_id,
            product_id="a",
            acquired=date(2026, 5, 1),
            anomalies=[_anomaly("r1c1")],
            zones=[_zone("r1c1", CELL)],
        )
        second = _obs(
            parcel_id=parcel_id,
            product_id="b",
            acquired=date(2026, 7, 1),
            anomalies=[_anomaly("r1c1")],
            zones=[_zone("r1c1", CELL)],
        )
        result = build_satellite_history([first, second], parcel_id=parcel_id)
        self.assertEqual(result["repeated_anomalies"][0]["relation"], "same_grid_cell")

    def test_single_anomaly_is_not_called_repeated(self) -> None:
        parcel_id = uuid4()
        only = _obs(
            parcel_id=parcel_id,
            product_id="a",
            acquired=date(2026, 5, 1),
            anomalies=[_anomaly("r0c0")],
            zones=[_zone("r0c0", CELL)],
        )
        later = _obs(
            parcel_id=parcel_id,
            product_id="b",
            acquired=date(2026, 6, 1),
            cloud=Decimal("50"),
            ndvi=None,
        )
        result = build_satellite_history([only, later], parcel_id=parcel_id)
        self.assertEqual(result["repeated_anomalies"], [])
        self.assertTrue(any("nema zone koja se ponavlja" in note for note in result["notes"]))
