from decimal import Decimal
from unittest import TestCase

from app.services.expected_yield_calc import (
    compare_actual_to_expected,
    compute_expected_yield,
    planting_age_year,
)
from app.yield_curve.expected_yield_profile import (
    ExpectedYieldScenario,
    SHELL_TO_NET_RATIO,
    kg_per_tree_for_age,
    shell_to_net,
)


class ExpectedYieldCalcTests(TestCase):
    def test_planting_year_is_curve_year_one(self) -> None:
        self.assertEqual(planting_age_year(2022, 2022), 1)
        self.assertEqual(planting_age_year(2022, 2026), 5)
        self.assertIsNone(planting_age_year(2025, 2024))

    def test_curve_values(self) -> None:
        self.assertEqual(kg_per_tree_for_age(4, ExpectedYieldScenario.REALISTIC), Decimal("0.5"))
        self.assertEqual(kg_per_tree_for_age(5, ExpectedYieldScenario.REALISTIC), Decimal("1.5"))
        self.assertEqual(kg_per_tree_for_age(6, ExpectedYieldScenario.REALISTIC), Decimal("2.5"))
        self.assertEqual(kg_per_tree_for_age(20, ExpectedYieldScenario.REALISTIC), Decimal("8.0"))

    def test_single_age_parcel(self) -> None:
        totals = compute_expected_yield(
            distribution={2022: 100},
            unknown_tree_count=0,
            reference_year=2026,  # age year 5
        )
        self.assertTrue(totals.available)
        self.assertFalse(totals.mixed_ages)
        self.assertEqual(totals.age_years, (5,))
        self.assertEqual(totals.realistic_kg, Decimal("150.0"))  # 100 × 1.5 bruto
        self.assertEqual(totals.realistic_net_kg, Decimal("60.00"))  # 40% bruto
        self.assertEqual(totals.shell_to_net_ratio, SHELL_TO_NET_RATIO)

    def test_multi_year_cohorts(self) -> None:
        # 100@age4 + 200@age5 + 300@age6 in reference 2026
        # planting 2023→4, 2022→5, 2021→6
        totals = compute_expected_yield(
            distribution={2023: 100, 2022: 200, 2021: 300},
            unknown_tree_count=0,
            reference_year=2026,
        )
        self.assertTrue(totals.available)
        self.assertTrue(totals.mixed_ages)
        self.assertEqual(totals.realistic_kg, Decimal("1100.0"))
        self.assertEqual(totals.realistic_net_kg, Decimal("440.00"))

    def test_missing_planting_data(self) -> None:
        totals = compute_expected_yield(
            distribution={},
            unknown_tree_count=50,
            reference_year=2026,
        )
        self.assertFalse(totals.available)
        self.assertIsNotNone(totals.message)
        self.assertIn("50", totals.precision_note or "")

    def test_partial_known_trees(self) -> None:
        totals = compute_expected_yield(
            distribution={2022: 80},
            unknown_tree_count=20,
            reference_year=2026,
        )
        self.assertTrue(totals.available)
        self.assertEqual(totals.known_tree_count, 80)
        self.assertIn("80 od 100", totals.precision_note or "")

    def test_kg_per_hectare(self) -> None:
        totals = compute_expected_yield(
            distribution={2022: 100},
            unknown_tree_count=0,
            reference_year=2026,
            area_hectares=Decimal("2"),
        )
        self.assertEqual(totals.expected_per_hectare_realistic, Decimal("75.00"))
        self.assertEqual(totals.expected_per_hectare_realistic_net, Decimal("30.00"))

    def test_shell_to_net(self) -> None:
        self.assertEqual(shell_to_net(Decimal("150")), Decimal("60.00"))
        self.assertIsNone(shell_to_net(None))

    def test_actual_below_expected(self) -> None:
        # pessimistic gross 6300 → net 2520; actual 2268 → ~10% below
        comparison = compare_actual_to_expected(Decimal("2268"), Decimal("6300"))
        self.assertEqual(comparison.expected_pessimistic_net_kg, Decimal("2520.00"))
        self.assertEqual(comparison.difference_kg, Decimal("-252.00"))
        self.assertEqual(comparison.difference_percent, Decimal("-10.0"))
        self.assertIn("ispod", comparison.message or "")
        self.assertIn("pesimističn", comparison.message or "")

    def test_actual_above_expected(self) -> None:
        # pessimistic gross 6250 → net 2500; actual 2720 → 8.8% above
        comparison = compare_actual_to_expected(Decimal("2720"), Decimal("6250"))
        self.assertEqual(comparison.expected_pessimistic_net_kg, Decimal("2500.00"))
        self.assertEqual(comparison.difference_percent, Decimal("8.8"))
        self.assertIn("iznad", comparison.message or "")

    def test_zero_expected_no_percent(self) -> None:
        comparison = compare_actual_to_expected(Decimal("10"), Decimal("0"))
        self.assertEqual(comparison.expected_pessimistic_net_kg, Decimal("0.00"))
        self.assertEqual(comparison.difference_kg, Decimal("10"))
        self.assertIsNone(comparison.difference_percent)

    def test_no_actual_yet(self) -> None:
        comparison = compare_actual_to_expected(None, Decimal("1500"))
        self.assertEqual(comparison.expected_pessimistic_net_kg, Decimal("600.00"))
        self.assertIsNone(comparison.difference_kg)
        self.assertIsNone(comparison.message)
