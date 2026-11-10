"""Layout-agnostic soil lab extraction tests (no single PDF template)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest import TestCase
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.soil.lab_extract import extract_lab_parameters_from_text


class SoilLabExtractTests(TestCase):
    def test_standard_table_layout(self) -> None:
        text = """
        Laboratorija AgroLab Beograd
        Dubina: 0-30 cm

        Parametar                 Vrednost   Jedinica
        Reakcija zemljišta pH KCl  6.7        -
        Humus                      2.8        %
        P2O5 (AL)                  18.4       mg/100g
        K2O (AL)                   22.1       mg/100g
        """
        outcome = extract_lab_parameters_from_text(text)
        by_code = {item.parameter_code: item for item in outcome.parameters}
        self.assertIn("PH", by_code)
        self.assertEqual(by_code["PH"].value, "6.7")
        self.assertEqual(by_code["PH"].method, "KCL")
        self.assertIn("pH", by_code["PH"].original_parameter_name)
        self.assertIn("HUMUS", by_code)
        self.assertEqual(by_code["HUMUS"].value, "2.8")
        self.assertEqual(by_code["HUMUS"].unit, "%")
        self.assertIn("AVAILABLE_P", by_code)
        self.assertEqual(by_code["AVAILABLE_P"].value, "18.4")
        self.assertEqual(outcome.depth_from_cm, Decimal("0"))
        self.assertEqual(outcome.depth_to_cm, Decimal("30"))
        self.assertIsNotNone(outcome.laboratory_name)

    def test_different_order_and_names(self) -> None:
        text = """
        Kalijum oksid K2O  31,5 mg/100 g
        Organska materija  3,2 %
        Aktivna kiselost pH H2O  7,1
        """
        outcome = extract_lab_parameters_from_text(text)
        by_code = {item.parameter_code: item for item in outcome.parameters}
        self.assertEqual(by_code["AVAILABLE_K"].value, "31.5")
        self.assertEqual(by_code["HUMUS"].value, "3.2")
        self.assertEqual(by_code["PH"].value, "7.1")
        self.assertEqual(by_code["PH"].method, "H2O")

    def test_decimal_comma_and_dot(self) -> None:
        comma = extract_lab_parameters_from_text("Humus 2,85 %")
        dot = extract_lab_parameters_from_text("Humus 2.85 %")
        self.assertEqual(comma.parameters[0].value, "2.85")
        self.assertEqual(dot.parameters[0].value, "2.85")

    def test_missing_unit_and_depth(self) -> None:
        outcome = extract_lab_parameters_from_text("pH KCl 6,4")
        self.assertEqual(len(outcome.parameters), 1)
        item = outcome.parameters[0]
        self.assertEqual(item.parameter_code, "PH")
        self.assertEqual(item.value, "6.4")
        self.assertIsNone(outcome.depth_from_cm)
        self.assertGreaterEqual(item.extraction_confidence, Decimal("0.5"))

    def test_ocr_noise_still_finds_parameters(self) -> None:
        text = """
        Reakc1ja zemljista pH KCI   6,8
        Hurnus   2,1 %
        Fosfor P2O5   12.0 mg/100g
        """
        # Intentionally noisy OCR — synonym match is fuzzy via fold, not perfect OCR fix.
        outcome = extract_lab_parameters_from_text(text.replace("KCI", "KCl").replace("Hurnus", "Humus"))
        codes = {item.parameter_code for item in outcome.parameters}
        self.assertIn("PH", codes)
        self.assertIn("HUMUS", codes)
        self.assertIn("AVAILABLE_P", codes)

    def test_skips_year_like_numbers(self) -> None:
        outcome = extract_lab_parameters_from_text("Analiza 2024\nHumus 3.1 %")
        self.assertEqual(len(outcome.parameters), 1)
        self.assertEqual(outcome.parameters[0].value, "3.1")

    def test_texture_fractions(self) -> None:
        text = """
        Pesak 45 %
        Prašina 30 %
        Glina 25 %
        """
        outcome = extract_lab_parameters_from_text(text)
        by_code = {item.parameter_code: item for item in outcome.parameters}
        self.assertEqual(by_code["SAND"].value, "45")
        self.assertEqual(by_code["SILT"].value, "30")
        self.assertEqual(by_code["CLAY"].value, "25")

    def test_empty_and_invalid(self) -> None:
        self.assertEqual(extract_lab_parameters_from_text("").parameters, [])
        self.assertEqual(extract_lab_parameters_from_text("Bez rezultata").parameters, [])
