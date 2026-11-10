from decimal import Decimal
from unittest import TestCase

from app.satellite.indices import INDEX_FORMULAS, ndre, ndvi, ndwi_gao, decimal_or_none
from app.satellite.selection import select_best_image
from app.satellite.anomalies import ZoneSnapshot, detect_anomalies
from app.satellite.providers.fake import FakeSatelliteProvider
from app.satellite.zones import build_zone_grid
from app.models.enums import SatelliteAnomalyKind


SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [
            [20.0, 44.0],
            [20.01, 44.0],
            [20.01, 44.01],
            [20.0, 44.01],
            [20.0, 44.0],
        ]
    ],
}


class SatelliteIndexTests(TestCase):
    def test_ndvi_formula(self) -> None:
        self.assertAlmostEqual(ndvi(0.8, 0.2) or 0, 0.6, places=6)
        self.assertIsNone(ndvi(0.0, 0.0))
        self.assertIn("B08", INDEX_FORMULAS["ndvi"])
        self.assertIn("B04", INDEX_FORMULAS["ndvi"])

    def test_ndre_uses_b8a_and_b05(self) -> None:
        self.assertAlmostEqual(ndre(0.7, 0.3) or 0, 0.4, places=6)
        self.assertIn("B8A", INDEX_FORMULAS["ndre"])
        self.assertIn("B05", INDEX_FORMULAS["ndre"])

    def test_ndwi_is_gao_not_mcfeeters(self) -> None:
        self.assertAlmostEqual(ndwi_gao(0.6, 0.2) or 0, 0.5, places=6)
        self.assertIn("NDWI_GAO", INDEX_FORMULAS["ndwi"])
        self.assertIn("B11", INDEX_FORMULAS["ndwi"])

    def test_decimal_or_none(self) -> None:
        self.assertEqual(decimal_or_none(0.1234), Decimal("0.1234"))
        self.assertIsNone(decimal_or_none(None))


class SatelliteSelectionTests(TestCase):
    def setUp(self) -> None:
        self.provider = FakeSatelliteProvider()

    def test_prefers_newest_under_lowest_threshold(self) -> None:
        from datetime import date

        candidate, threshold = select_best_image(
            self.provider,
            SQUARE,
            date(2026, 8, 1),
            date(2026, 8, 31),
            cloud_thresholds=(20.0, 30.0, 40.0),
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertLessEqual(candidate.cloud_cover or 0, threshold or 100)
        self.assertEqual(candidate.acquisition_date.month, 8)

    def test_progressive_cloud_thresholds(self) -> None:
        from datetime import date

        # Force only high-cloud scenes by using max_cloud that finds nothing at 20.
        class CloudyOnly(FakeSatelliteProvider):
            def search_available_images(self, parcel_geometry, start_date, end_date, max_cloud_cover):
                items = super().search_available_images(
                    parcel_geometry, start_date, end_date, max_cloud_cover=100
                )
                return [item for item in items if (item.cloud_cover or 0) > 20 and (item.cloud_cover or 0) <= max_cloud_cover]

        candidate, threshold = select_best_image(
            CloudyOnly(),
            SQUARE,
            date(2026, 8, 1),
            date(2026, 8, 31),
            cloud_thresholds=(20.0, 30.0, 40.0),
        )
        self.assertIsNotNone(candidate)
        self.assertGreaterEqual(threshold or 0, 30.0)


class SatelliteZoneTests(TestCase):
    def test_grid_produces_zones(self) -> None:
        zones = build_zone_grid(SQUARE, grid_size=3)
        self.assertGreaterEqual(len(zones), 1)
        self.assertTrue(all(key.startswith("r") for key, _ in zones))


class SatelliteAnomalyTests(TestCase):
    def test_below_mean_and_sudden_decline(self) -> None:
        findings = detect_anomalies(
            parcel_ndvi_mean=Decimal("0.60"),
            current_zones=[
                ZoneSnapshot(zone_key="r0c0", ndvi=Decimal("0.40")),
                ZoneSnapshot(zone_key="r0c1", ndvi=Decimal("0.62")),
            ],
            previous_zones=[
                ZoneSnapshot(zone_key="r0c0", ndvi=Decimal("0.58")),
                ZoneSnapshot(zone_key="r0c1", ndvi=Decimal("0.61")),
            ],
            below_mean_fraction=0.15,
            sudden_decline_fraction=0.20,
        )
        kinds = {item.kind for item in findings}
        self.assertIn(SatelliteAnomalyKind.BELOW_PARCEL_MEAN, kinds)
        self.assertIn(SatelliteAnomalyKind.SUDDEN_DECLINE, kinds)
        self.assertTrue(all("slabije" in item.message.lower() for item in findings))

    def test_persistent_low(self) -> None:
        findings = detect_anomalies(
            parcel_ndvi_mean=Decimal("0.60"),
            current_zones=[ZoneSnapshot(zone_key="r0c0", ndvi=Decimal("0.40"))],
            previous_zones=[ZoneSnapshot(zone_key="r0c0", ndvi=Decimal("0.42"))],
            previous_previous_zones=[ZoneSnapshot(zone_key="r0c0", ndvi=Decimal("0.41"))],
            below_mean_fraction=0.15,
        )
        kinds = [item.kind for item in findings]
        self.assertIn(SatelliteAnomalyKind.PERSISTENT_LOW, kinds)


class FakeProviderTests(TestCase):
    def test_calculate_indices(self) -> None:
        from datetime import date

        from app.satellite.indices import IndexName

        provider = FakeSatelliteProvider()
        images = provider.search_available_images(SQUARE, date(2026, 9, 1), date(2026, 9, 20), 20)
        self.assertTrue(images)
        result = provider.calculate_indices(
            SQUARE,
            images[0].image_id,
            [IndexName.NDVI, IndexName.NDRE, IndexName.NDWI],
        )
        self.assertIsNotNone(result.ndvi.mean)
        self.assertGreater(len(result.zones), 0)
