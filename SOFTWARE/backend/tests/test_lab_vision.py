"""Model reading of a soil report. No OCR and no invented zeros."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.knowledge.pdf import build_text_pdf
from app.soil.lab_vision import format_lab_reading, parse_lab_reading, read_lab_document, remembered_lab_block


class LabVisionTests(unittest.TestCase):
    def test_parse_keeps_only_known_parameters(self) -> None:
        raw = """
        {
          "laboratory_name": "Lab Agro",
          "sampled_on": "2026-03-12",
          "summary": "pH je blago kiseo.",
          "parameters": [
            {"code": "PH", "name": "pH u KCl", "value": "6.2", "unit": null, "method": "KCl"},
            {"code": "NOT_A_CODE", "name": "X", "value": "1", "unit": null, "method": null},
            {"code": "AVAILABLE_P", "name": "P2O5", "value": "", "unit": "mg/100g", "method": null}
          ]
        }
        """
        reading = parse_lab_reading(raw)
        self.assertEqual(reading["laboratory_name"], "Lab Agro")
        self.assertEqual(reading["sampled_on"], "2026-03-12")
        self.assertEqual([item["code"] for item in reading["parameters"]], ["PH"])
        self.assertEqual(reading["parameters"][0]["value"], "6.2")

    def test_missing_value_is_not_zero(self) -> None:
        reading = parse_lab_reading('{"parameters": [{"code": "HUMUS", "value": null}]}')
        self.assertEqual(reading["parameters"], [])
        self.assertIsNone(format_lab_reading(reading))

    def test_later_turn_still_sees_the_saved_reading(self) -> None:
        message = SimpleNamespace(
            structured_refs=[
                {
                    "kind": "chat_document",
                    "label": "analiza.pdf",
                    "extra": {
                        "lab_reading": {
                            "summary": "Fosfor je nizak.",
                            "parameters": [
                                {"code": "AVAILABLE_P", "name": "P2O5", "value": "8", "unit": "mg/100g"}
                            ],
                        }
                    },
                }
            ]
        )
        block = remembered_lab_block([message])
        self.assertIsNotNone(block)
        assert block is not None
        self.assertIn("analiza.pdf", block)
        self.assertIn("8", block)
        self.assertIn("ne tražite ponovo", block.lower())
        doubled = remembered_lab_block([message, message])
        assert doubled is not None
        self.assertEqual(doubled.count("analiza.pdf"), 1)

    def test_text_pdf_goes_to_the_model_as_text(self) -> None:
        pdf = build_text_pdf("Analiza zemljista", [("Rezultat", "pH u KCl 6.4 " * 12)])
        seen: list[object] = []

        class Provider:
            def chat(self, messages, **kwargs):
                del kwargs
                seen.append(messages[-1].content)
                return SimpleNamespace(
                    content='{"summary":"pH je 6.4.","parameters":[{"code":"PH","name":"pH","value":"6.4"}]}'
                )

        reading = read_lab_document(Provider(), pdf, "application/pdf")
        self.assertIsInstance(seen[0], str)
        self.assertNotIn("image_url", str(seen[0]))
        self.assertEqual(reading["parameters"][0]["value"], "6.4")


if __name__ == "__main__":
    unittest.main()
