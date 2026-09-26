from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest import TestCase
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.activity import ActivityLineItem
from app.services.activity import (
    _cost_category_for_activity,
    _cost_category_for_line_item,
    _line_item_cost,
    _line_item_has_value,
)


class ActivityLineItemCalcTests(TestCase):
    def test_amount_creates_cost(self) -> None:
        item = ActivityLineItem(name="Nafta", quantity=Decimal("12"), unit="L", amount=Decimal("45.50"))
        self.assertEqual(_line_item_cost(item), Decimal("45.50"))

    def test_legacy_eur_unit_still_creates_cost(self) -> None:
        item = ActivityLineItem(quantity=Decimal("20"), unit="EUR")
        self.assertEqual(_line_item_cost(item), Decimal("20"))

    def test_zero_or_missing_amount_is_ignored(self) -> None:
        self.assertIsNone(_line_item_cost(ActivityLineItem(name="Nafta", quantity=Decimal("5"), unit="L")))
        self.assertIsNone(_line_item_cost(ActivityLineItem(amount=Decimal("0"))))

    def test_cost_categories_follow_activity_type(self) -> None:
        self.assertEqual(_cost_category_for_activity("irrigation"), "fuel")
        self.assertEqual(_cost_category_for_activity("spraying"), "plant_protection")
        self.assertEqual(_cost_category_for_activity("fertilization"), "fertilizers")
        self.assertEqual(_cost_category_for_activity("pruning"), "other")

    def test_irrigation_equipment_uses_equipment_category(self) -> None:
        fuel = ActivityLineItem(name="Nafta", quantity=Decimal("12"), unit="L", amount=Decimal("45.50"))
        hose = ActivityLineItem(name="Kap po kap crevo", quantity=Decimal("200"), unit="m", amount=Decimal("80"))
        self.assertEqual(_cost_category_for_line_item("irrigation", fuel), "fuel")
        self.assertEqual(_cost_category_for_line_item("irrigation", hose), "equipment")
        self.assertEqual(_cost_category_for_line_item("spraying", hose), "plant_protection")

    def test_named_irrigation_row_is_kept(self) -> None:
        item = ActivityLineItem(name="Pumpa", quantity=Decimal("1"), unit="kom")
        self.assertTrue(_line_item_has_value(item))
