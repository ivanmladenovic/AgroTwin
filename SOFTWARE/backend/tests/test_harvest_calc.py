from datetime import date
from decimal import Decimal
from unittest import TestCase

from app.models.enums import HarvestQualityCategory
from app.services.harvest_calc import (
    HarvestMeasure,
    available_production_years,
    first_last_dates,
    net_quantity,
    parcel_scope_only,
    quality_from_measures,
    timeline_points,
    total_kg,
    validate_quantities,
    weighted_average,
    yield_per_hectare,
    yield_per_tree,
)


def _event(**kwargs) -> HarvestMeasure:
    payload = {
        "scope_type": "parcel",
        "harvested_on": date(2026, 9, 10),
        "gross": Decimal("500"),
        "loss": Decimal("20"),
        "unit": "kg",
    }
    payload.update(kwargs)
    return HarvestMeasure(**payload)


class QuantityTests(TestCase):
    def test_net_subtracts_loss(self) -> None:
        self.assertEqual(net_quantity(Decimal("1500"), Decimal("80")), Decimal("1420"))

    def test_missing_loss_equals_gross(self) -> None:
        self.assertEqual(net_quantity(Decimal("500"), None), Decimal("500"))

    def test_invalid_loss_greater_than_gross(self) -> None:
        with self.assertRaises(ValueError):
            validate_quantities(Decimal("100"), Decimal("120"))

    def test_invalid_zero_gross(self) -> None:
        with self.assertRaises(ValueError):
            validate_quantities(Decimal("0"), Decimal("0"))


class AggregationTests(TestCase):
    def test_multiple_parcel_harvests_sum_net(self) -> None:
        events = [
            _event(harvested_on=date(2026, 9, 10), gross=Decimal("500"), loss=Decimal("20")),
            _event(harvested_on=date(2026, 9, 15), gross=Decimal("650"), loss=Decimal("30")),
            _event(harvested_on=date(2026, 9, 20), gross=Decimal("330"), loss=Decimal("10")),
        ]
        self.assertEqual(total_kg(events, "net"), Decimal("1420"))
        self.assertEqual(total_kg(events, "gross"), Decimal("1480"))
        self.assertEqual(total_kg(events, "loss"), Decimal("60"))
        first, last = first_last_dates(events)
        self.assertEqual(first, date(2026, 9, 10))
        self.assertEqual(last, date(2026, 9, 20))

    def test_row_and_tree_do_not_enter_parcel_total(self) -> None:
        events = [
            _event(gross=Decimal("1000"), loss=Decimal("0")),
            _event(scope_type="row", gross=Decimal("100"), loss=Decimal("0")),
            _event(scope_type="tree", gross=Decimal("3"), loss=Decimal("0")),
        ]
        self.assertEqual(total_kg(parcel_scope_only(events), "net"), Decimal("1000"))
        self.assertEqual(total_kg(events, "net"), Decimal("1103"))

    def test_empty_year_is_none_not_zero(self) -> None:
        self.assertIsNone(total_kg([], "net"))
        first, last = first_last_dates([])
        self.assertIsNone(first)
        self.assertIsNone(last)

    def test_yield_per_hectare_and_tree(self) -> None:
        self.assertEqual(yield_per_hectare(Decimal("1420"), Decimal("4.75")), Decimal("298.95"))
        self.assertEqual(yield_per_tree(Decimal("1420"), 1891), Decimal("0.75"))
        self.assertIsNone(yield_per_tree(Decimal("1420"), 0))
        self.assertIsNone(yield_per_hectare(Decimal("1420"), None))

    def test_timeline_aggregates_same_date_and_cumulative(self) -> None:
        events = [
            _event(harvested_on=date(2026, 9, 10), gross=Decimal("500"), loss=Decimal("0")),
            _event(harvested_on=date(2026, 9, 15), gross=Decimal("620"), loss=Decimal("0")),
            _event(harvested_on=date(2026, 9, 15), gross=Decimal("80"), loss=Decimal("0")),
        ]
        points = timeline_points(events)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["net_kg"], Decimal("500"))
        self.assertEqual(points[1]["net_kg"], Decimal("700"))
        self.assertEqual(points[1]["event_count"], 2)
        self.assertEqual(points[1]["cumulative_net_kg"], Decimal("1200"))


class QualityTests(TestCase):
    def test_weighted_moisture_by_net_quantity(self) -> None:
        events = [
            _event(gross=Decimal("500"), loss=Decimal("20"), moisture_percent=Decimal("8.5")),
            _event(harvested_on=date(2026, 9, 15), gross=Decimal("650"), loss=Decimal("30"), moisture_percent=Decimal("8.2")),
            _event(harvested_on=date(2026, 9, 20), gross=Decimal("330"), loss=Decimal("10"), moisture_percent=Decimal("9.4")),
        ]
        quality = quality_from_measures(events)
        self.assertTrue(quality["moisture"]["available"])
        self.assertEqual(quality["moisture"]["method"], "weighted")
        self.assertEqual(quality["moisture"]["value"], Decimal("8.6"))

    def test_quality_categories_sum_net(self) -> None:
        events = [
            _event(gross=Decimal("980"), loss=Decimal("30"), quality_category=HarvestQualityCategory.STANDARD),
            _event(
                harvested_on=date(2026, 9, 15),
                gross=Decimal("360"),
                loss=Decimal("10"),
                quality_category=HarvestQualityCategory.PREMIUM,
            ),
        ]
        quality = quality_from_measures(events)
        by_category = {item["category"]: item["net_kg"] for item in quality["categories"]}
        self.assertEqual(by_category[HarvestQualityCategory.STANDARD], Decimal("950"))
        self.assertEqual(by_category[HarvestQualityCategory.PREMIUM], Decimal("350"))

    def test_no_quality_is_unrecorded(self) -> None:
        quality = quality_from_measures([_event()])
        self.assertFalse(quality["recorded"])
        self.assertFalse(quality["moisture"]["available"])


class YearHelperTests(TestCase):
    def test_available_years_are_not_hardcoded(self) -> None:
        years = available_production_years([2024], selected_year=2026, current_year=2026, planting_year=2022)
        self.assertIn(2022, years)
        self.assertIn(2024, years)
        self.assertIn(2025, years)
        self.assertIn(2026, years)
        self.assertIn(2027, years)

    def test_weighted_average_ignores_zero_weight(self) -> None:
        self.assertIsNone(weighted_average([(Decimal("8"), Decimal("0"))]))
        self.assertEqual(weighted_average([(Decimal("10"), Decimal("2")), (Decimal("4"), Decimal("2"))]), Decimal("7.0"))
