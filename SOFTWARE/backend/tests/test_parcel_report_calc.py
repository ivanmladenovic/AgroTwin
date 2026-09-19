from datetime import date
from decimal import Decimal
from unittest import TestCase

from app.services.parcel_report_calc import (
    build_executive_summary,
    change_direction,
    change_tone,
    mass_to_kg,
    money,
    percent_change,
    pick_monthly_highlights,
    ratio,
    year_bounds,
    yield_kg_from_line_items,
)


class YearBoundsTests(TestCase):
    def test_calendar_year(self) -> None:
        start, end = year_bounds(2026)
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 12, 31))


class PercentChangeTests(TestCase):
    def test_increase(self) -> None:
        self.assertEqual(percent_change(Decimal("4820"), Decimal("4285")), Decimal("12.5"))

    def test_decrease(self) -> None:
        self.assertEqual(percent_change(Decimal("24"), Decimal("29")), Decimal("-17.2"))

    def test_missing_previous_is_unavailable(self) -> None:
        self.assertIsNone(percent_change(Decimal("10"), None))

    def test_zero_previous_is_unavailable(self) -> None:
        self.assertIsNone(percent_change(Decimal("10"), Decimal("0")))


class ChangeToneTests(TestCase):
    def test_higher_yield_is_positive(self) -> None:
        self.assertEqual(change_direction(Decimal("1420"), Decimal("1305")), "up")
        self.assertEqual(change_tone("yield_kg", "up"), "positive")

    def test_fewer_problems_is_positive(self) -> None:
        self.assertEqual(change_tone("problem_cases", "down"), "positive")
        self.assertEqual(change_tone("attention_trees", "up"), "negative")

    def test_higher_costs_are_neutral(self) -> None:
        self.assertEqual(change_tone("annual_cost", "up"), "neutral")
        self.assertEqual(change_tone("activities_completed", "up"), "neutral")


class YieldAggregationTests(TestCase):
    def test_kg_line_items_ignore_eur(self) -> None:
        kg = yield_kg_from_line_items(
            [
                {"quantity": "1850", "unit": "kg"},
                {"quantity": "3340.00", "unit": "EUR"},
            ]
        )
        self.assertEqual(kg, Decimal("1850"))

    def test_tonnes_convert_to_kg(self) -> None:
        self.assertEqual(mass_to_kg("2.2", "t"), Decimal("2200.0"))

    def test_missing_yield_is_none_not_zero(self) -> None:
        self.assertIsNone(yield_kg_from_line_items([{"quantity": "420", "unit": "L"}]))
        self.assertIsNone(yield_kg_from_line_items([]))


class RatioTests(TestCase):
    def test_missing_denominator_is_unavailable(self) -> None:
        self.assertIsNone(ratio(Decimal("4820"), None))
        self.assertIsNone(ratio(Decimal("4820"), 0))


class TimelineTests(TestCase):
    def test_one_highlight_per_month_prefers_harvest(self) -> None:
        items = pick_monthly_highlights(
            [
                {
                    "performed_on": date(2026, 9, 2),
                    "title": "Pregled",
                    "name": "Pregled",
                    "slug": "inspection",
                },
                {
                    "performed_on": date(2026, 9, 26),
                    "title": "Berba",
                    "name": "Berba",
                    "slug": "harvesting",
                },
                {
                    "performed_on": date(2026, 4, 8),
                    "title": "Đubrenje",
                    "name": "Đubrenje",
                    "slug": "fertilization",
                },
            ]
        )
        self.assertEqual([item["title"] for item in items], ["Đubrenje", "Berba"])


class ExecutiveSummaryTests(TestCase):
    def test_uses_actual_values(self) -> None:
        text = build_executive_summary(
            year=2026,
            previous_year=2025,
            parcel_name="Kusiljevo",
            activities_completed=49,
            annual_cost=Decimal("4820"),
            costs_available=True,
            yield_kg=Decimal("1420"),
            yield_change_percent=Decimal("8.8"),
            attention_count=24,
            top_problem_row=12,
        )
        self.assertIn("49 urađenih aktivnosti", text)
        self.assertIn(money(Decimal("4820")), text)
        self.assertIn("8.8%", text)
        self.assertIn("24 stabala", text)
        self.assertIn("redu 12", text)

    def test_omits_invented_yield(self) -> None:
        text = build_executive_summary(
            year=2026,
            previous_year=2025,
            parcel_name="Kusiljevo",
            activities_completed=12,
            annual_cost=Decimal("100"),
            costs_available=True,
            yield_kg=None,
            yield_change_percent=None,
            attention_count=1,
            top_problem_row=None,
        )
        self.assertNotIn("Prinos", text)
        self.assertIn("1 stablo", text)
