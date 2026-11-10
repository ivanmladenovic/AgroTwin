from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest import TestCase
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.workforce import compute_labor_cost


class LaborCostCalcTests(TestCase):
    def test_hours_times_rate(self) -> None:
        self.assertEqual(compute_labor_cost(Decimal("3.5"), Decimal("15.00")), Decimal("52.50"))

    def test_quantizes_to_cents(self) -> None:
        self.assertEqual(compute_labor_cost(Decimal("1.333"), Decimal("10.00")), Decimal("13.33"))
