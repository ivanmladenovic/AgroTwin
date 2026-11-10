from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from app.satellite.zone_trees import (
    format_tree_ids_label,
    rewrite_zone_keys_in_text,
    trees_for_zone_keys,
    trees_in_zone_geometry,
)


def _square(west: float, south: float, east: float, north: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
        ],
    }


class ZoneTreesTests(TestCase):
    def test_trees_inside_zone(self) -> None:
        geometry = _square(20.0, 44.0, 20.2, 44.2)
        trees = [
            SimpleNamespace(public_id="R01-T0001", longitude=20.1, latitude=44.1),
            SimpleNamespace(public_id="R01-T0002", longitude=21.0, latitude=45.0),
            SimpleNamespace(public_id="R02-T0003", longitude=None, latitude=None),
        ]
        found = trees_in_zone_geometry(geometry, trees)
        self.assertEqual(found, ["R01-T0001"])

    def test_trees_for_zone_keys(self) -> None:
        zones = [
            SimpleNamespace(zone_key="r0c0", geometry=_square(20.0, 44.0, 20.2, 44.2)),
            SimpleNamespace(zone_key="r0c1", geometry=_square(20.3, 44.0, 20.5, 44.2)),
        ]
        trees = [
            SimpleNamespace(public_id="R01-T0001", longitude=20.1, latitude=44.1),
            SimpleNamespace(public_id="R01-T0002", longitude=20.4, latitude=44.1),
        ]
        found = trees_for_zone_keys(zone_keys=["r0c0", "r0c1"], zones=zones, trees=trees)
        self.assertEqual(found, ["R01-T0001", "R01-T0002"])
        self.assertEqual(format_tree_ids_label(found), "R01-T0001, R01-T0002")

    def test_schematic_trees_map_via_boundary(self) -> None:
        boundary = _square(20.0, 44.0, 20.4, 44.4)
        zone = _square(20.0, 44.0, 20.2, 44.2)
        trees = [
            SimpleNamespace(
                public_id="R01-T0001",
                longitude=None,
                latitude=None,
                normalized_x=0.0,
                normalized_y=0.0,
            ),
            SimpleNamespace(
                public_id="R02-T0001",
                longitude=None,
                latitude=None,
                normalized_x=10.0,
                normalized_y=10.0,
            ),
        ]
        found = trees_in_zone_geometry(zone, trees, parcel_boundary=boundary)
        self.assertEqual(found, ["R01-T0001"])

    def test_rewrite_zone_keys(self) -> None:
        text = "Najslabije u zoni r3c0, zatim r2c0."
        rewritten = rewrite_zone_keys_in_text(
            text,
            {"r3c0": ["R04-T0001", "R04-T0002"], "r2c0": ["R03-T0005"]},
        )
        self.assertIn("R04-T0001 (+1)", rewritten)
        self.assertIn("R03-T0005", rewritten)
        self.assertNotIn("r3c0", rewritten.lower())
