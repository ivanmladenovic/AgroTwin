"""Satellite coverage buckets. Missing scenes stay distinct from anomalies."""

from __future__ import annotations

import unittest

from app.enterprise.csv_safe import csv_cell
from app.enterprise.data_quality import business_buckets, satellite_buckets


class SatelliteBucketTests(unittest.TestCase):
    def test_no_scene_is_not_a_vegetation_problem(self) -> None:
        buckets = satellite_buckets([])
        self.assertEqual(buckets, {"no_scene", "insufficient_history"})
        self.assertNotIn("usable_scene", buckets)
        self.assertNotIn("cloudy_only", buckets)

    def test_cloudy_scene_is_not_usable(self) -> None:
        buckets = satellite_buckets([("completed", 40.0), ("completed", None)])
        self.assertIn("cloudy_only", buckets)
        self.assertIn("insufficient_history", buckets)
        self.assertNotIn("usable_scene", buckets)
        self.assertNotIn("no_scene", buckets)

    def test_one_clear_scene_still_lacks_history(self) -> None:
        buckets = satellite_buckets([("completed", 12.0)])
        self.assertIn("usable_scene", buckets)
        self.assertIn("insufficient_history", buckets)

    def test_two_clear_scenes_can_be_compared(self) -> None:
        buckets = satellite_buckets([("completed", 10.0), ("completed", 29.9)])
        self.assertEqual(buckets, {"usable_scene"})

    def test_incomplete_uses_existing_fields_only(self) -> None:
        self.assertEqual(
            business_buckets(open_alert=False, missing_fields=["boundary"]),
            set(),
        )
        self.assertEqual(
            business_buckets(open_alert=True, missing_fields=["trees"]),
            {"open_alert", "incomplete"},
        )


class CsvFormulaTests(unittest.TestCase):
    def test_formula_prefix_and_empty(self) -> None:
        self.assertEqual(csv_cell(None), "")
        self.assertEqual(csv_cell("=SUM(A1)"), "'=SUM(A1)")
        self.assertEqual(csv_cell("+381"), "'+381")
        self.assertEqual(csv_cell("-1"), "'-1")
        self.assertEqual(csv_cell("@cmd"), "'@cmd")
        self.assertEqual(csv_cell("pH 6,4"), '"pH 6,4"')
        self.assertEqual(csv_cell("obično"), "obično")


if __name__ == "__main__":
    unittest.main()
