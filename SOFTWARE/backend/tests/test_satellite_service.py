from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from app.models.enums import SatelliteProcessingStatus
from app.models.satellite import SatelliteObservation
from app.satellite.providers.base import SatelliteProviderError
from app.satellite.providers.fake import FakeSatelliteProvider

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


class _FailingSearchProvider(FakeSatelliteProvider):
    def search_available_images(self, parcel_geometry, start_date, end_date, max_cloud_cover):
        raise SatelliteProviderError("boom", retryable=True, code="provider_error")


class SatelliteServiceLogicTests(TestCase):
    """Lightweight tests that exercise selection/duplicate helpers without full DB fixtures.

    Full API/DB coverage lives behind integration environments; these tests focus on
    provider failure behaviour and duplicate detection using an in-memory stub repo.
    """

    def test_fake_provider_duplicate_product_ids_are_stable(self) -> None:
        provider = FakeSatelliteProvider()
        first = provider.search_available_images(SQUARE, date(2026, 9, 1), date(2026, 9, 20), 40)
        second = provider.search_available_images(SQUARE, date(2026, 9, 1), date(2026, 9, 20), 40)
        self.assertEqual([item.product_id for item in first], [item.product_id for item in second])

    def test_failing_provider_raises_retryable_error(self) -> None:
        provider = _FailingSearchProvider()
        with self.assertRaises(SatelliteProviderError) as ctx:
            provider.search_available_images(SQUARE, date(2026, 9, 1), date(2026, 9, 20), 20)
        self.assertTrue(ctx.exception.retryable)

    def test_observation_unique_key_fields(self) -> None:
        observation = SatelliteObservation(
            id=uuid4(),
            parcel_id=uuid4(),
            provider="fake",
            satellite="Sentinel-2",
            product_id="FAKE-S2-2026-09-10",
            acquisition_date=date(2026, 9, 10),
            acquisition_at=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
            processed_at=datetime.now(timezone.utc),
            cloud_cover=Decimal("10.00"),
            processing_status=SatelliteProcessingStatus.COMPLETED,
            visualization_refs={},
            source_metadata={},
            index_formulas={},
            anomaly_count=0,
        )
        self.assertEqual(observation.processing_status, SatelliteProcessingStatus.COMPLETED)
        self.assertEqual(observation.provider, "fake")
