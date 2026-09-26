from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.soil.properties import (
    EXCLUDED_LAYERS,
    PROPERTY_BY_KEY,
    REQUESTED_LAYER_NAMES,
    canonical_depth_key,
    convert_scaled_value,
    extra_scale_for_display,
    map_requested_layers,
    parse_soilgrids_payload,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "soilgrids_query.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


class SoilPropertyMappingTests(TestCase):
    def test_official_layer_names(self) -> None:
        self.assertEqual(PROPERTY_BY_KEY["ph"].soilgrids_name, "phh2o")
        self.assertEqual(PROPERTY_BY_KEY["organic_carbon"].soilgrids_name, "soc")
        self.assertEqual(PROPERTY_BY_KEY["total_nitrogen"].soilgrids_name, "nitrogen")
        self.assertNotIn("ocs", REQUESTED_LAYER_NAMES)
        self.assertIn("ocs", EXCLUDED_LAYERS)

    def test_map_requested_layers_prefers_verified_names(self) -> None:
        available = {"bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc"}
        mapping = map_requested_layers(available)
        self.assertEqual(mapping["ph"], "phh2o")
        self.assertEqual(mapping["organic_carbon"], "soc")
        self.assertEqual(mapping["clay"], "clay")
        self.assertEqual(mapping["cec"], "cec")
        self.assertEqual(mapping["total_nitrogen"], "nitrogen")
        self.assertNotEqual(mapping["organic_carbon"], "ocs")


class SoilUnitConversionTests(TestCase):
    def test_d_factor_and_soc_percent(self) -> None:
        self.assertEqual(convert_scaled_value(65, 10, decimals=2), 6.5)
        self.assertEqual(convert_scaled_value(370, 10, decimals=1), 37.0)
        self.assertEqual(convert_scaled_value(496, 100, decimals=2), 4.96)
        spec = PROPERTY_BY_KEY["organic_carbon"]
        extra = extra_scale_for_display(spec, "g/kg")
        self.assertEqual(convert_scaled_value(338, 10, extra_scale=extra, decimals=2), 3.38)
        self.assertEqual(extra_scale_for_display(spec, "%"), 1.0)

    def test_live_fixture_conversions(self) -> None:
        parsed = parse_soilgrids_payload(_fixture())
        self.assertEqual(parsed.status, "ok")
        self.assertEqual(parsed.properties["ph"].depths["0-5cm"].value, 6.5)
        self.assertEqual(parsed.properties["clay"].depths["0-5cm"].value, 37.0)
        self.assertEqual(parsed.properties["sand"].depths["0-5cm"].value, 25.7)
        self.assertEqual(parsed.properties["silt"].depths["0-5cm"].value, 37.2)
        self.assertEqual(parsed.properties["organic_carbon"].depths["0-5cm"].value, 3.38)
        self.assertEqual(parsed.properties["organic_carbon"].depths["0-5cm"].unit, "%")
        self.assertEqual(parsed.properties["cec"].depths["0-5cm"].value, 26.5)
        self.assertEqual(parsed.properties["total_nitrogen"].depths["0-5cm"].value, 4.96)
        self.assertEqual(parsed.properties["ph"].depths["0-5cm"].uncertainty, 0.4)

    def test_quantiles_are_converted_not_used_as_main_value(self) -> None:
        payload = {
            "properties": {
                "layers": [
                    {
                        "name": "phh2o",
                        "unit_measure": {"d_factor": 10, "mapped_units": "pH*10", "target_units": "-"},
                        "depths": [
                            {
                                "label": "0-5cm",
                                "values": {"mean": 65, "uncertainty": 4, "Q0.05": 58, "Q0.95": 72},
                            }
                        ],
                    }
                ]
            }
        }
        parsed = parse_soilgrids_payload(payload)
        depth = parsed.properties["ph"].depths["0-5cm"]
        self.assertEqual(depth.value, 6.5)
        self.assertEqual(depth.lower, 5.8)
        self.assertEqual(depth.upper, 7.2)
        self.assertNotEqual(depth.value, depth.lower)


class SoilDepthParsingTests(TestCase):
    def test_label_and_range_object(self) -> None:
        self.assertEqual(canonical_depth_key("0-5cm"), "0-5cm")
        self.assertEqual(canonical_depth_key("0–5 cm"), "0-5cm")
        self.assertEqual(
            canonical_depth_key({"label": "5-15cm", "range": {"top_depth": 5, "bottom_depth": 15, "unit_depth": "cm"}}),
            "5-15cm",
        )
        self.assertEqual(
            canonical_depth_key({"range": {"top_depth": 100, "bottom_depth": 200, "unit_depth": "cm"}}),
            "100-200cm",
        )
        self.assertIsNone(canonical_depth_key("3-7cm"))

    def test_missing_depth_is_omitted(self) -> None:
        payload = deepcopy(_fixture())
        for layer in payload["properties"]["layers"]:
            if layer["name"] == "nitrogen":
                layer["depths"] = layer["depths"][:2]
        parsed = parse_soilgrids_payload(payload)
        self.assertEqual(list(parsed.properties["total_nitrogen"].depths), ["0-5cm", "5-15cm"])
        self.assertIn("0-5cm", parsed.properties["clay"].depths)
        self.assertIn("100-200cm", parsed.properties["clay"].depths)


class SoilPartialResponseTests(TestCase):
    def test_missing_property_does_not_drop_profile(self) -> None:
        payload = deepcopy(_fixture())
        payload["properties"]["layers"] = [layer for layer in payload["properties"]["layers"] if layer["name"] != "soc"]
        parsed = parse_soilgrids_payload(payload)
        self.assertEqual(parsed.status, "partial")
        self.assertIn("organic_carbon", parsed.missing_properties)
        self.assertIn("ph", parsed.properties)
        self.assertNotIn("organic_carbon", parsed.properties)

    def test_ocs_is_not_treated_as_organic_carbon(self) -> None:
        payload = {
            "properties": {
                "layers": [
                    {
                        "name": "ocs",
                        "unit_measure": {"d_factor": 10, "target_units": "t/ha"},
                        "depths": [{"label": "0-30cm", "values": {"mean": 540}}],
                    }
                ]
            }
        }
        parsed = parse_soilgrids_payload(payload)
        self.assertEqual(parsed.status, "malformed")
        self.assertNotIn("organic_carbon", parsed.properties)

    def test_malformed_payload(self) -> None:
        parsed = parse_soilgrids_payload({"hello": "world"})
        self.assertEqual(parsed.status, "malformed")
        self.assertEqual(parsed.properties, {})
