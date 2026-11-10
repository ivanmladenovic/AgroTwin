"""Unit tests for map editor geometry, metrics, and planting layout."""

from __future__ import annotations

import math

import pytest

from app.map_editor.geometry import has_self_intersection, place_points_on_segment, point_in_polygon
from app.map_editor.layout import generate_planting_layout
from app.map_editor.metrics import polygon_metrics
from app.map_editor.validation import MapEditorGeometryError, validate_editor_boundary


def _rect_polygon(lon0: float, lat0: float, width_m: float, height_m: float) -> dict:
    """Axis-aligned rectangle near Serbia (~44.8N, 21.1E) sized in meters."""
    m_lat = 111_320.0
    m_lon = 111_320.0 * math.cos(math.radians(lat0))
    dlon = width_m / m_lon
    dlat = height_m / m_lat
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon0, lat0],
                [lon0 + dlon, lat0],
                [lon0 + dlon, lat0 + dlat],
                [lon0, lat0 + dlat],
                [lon0, lat0],
            ]
        ],
    }


def test_rectangular_area_and_perimeter():
    geom = _rect_polygon(21.1, 44.8, 100.0, 50.0)
    metrics = polygon_metrics(geom)
    assert metrics["vertex_count"] == 4
    assert abs(metrics["area_m2"] - 5000.0) < 30.0  # equirectangular tolerance
    assert abs(metrics["area_ha"] - 0.5) < 0.01
    assert abs(metrics["perimeter_m"] - 300.0) < 5.0
    assert metrics["self_intersecting"] is False


def test_irregular_convex_polygon_metrics():
    geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [21.10, 44.80],
                [21.1015, 44.80],
                [21.1012, 44.801],
                [21.1002, 44.8008],
                [21.10, 44.80],
            ]
        ],
    }
    metrics = polygon_metrics(geom)
    assert metrics["vertex_count"] == 4
    assert metrics["area_m2"] > 0
    assert metrics["perimeter_m"] > 0


def test_self_intersecting_rejected():
    # Bow-tie
    geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [21.10, 44.80],
                [21.101, 44.801],
                [21.101, 44.80],
                [21.10, 44.801],
                [21.10, 44.80],
            ]
        ],
    }
    with pytest.raises(MapEditorGeometryError) as exc:
        validate_editor_boundary(geom)
    assert exc.value.code == "self_intersection"


def test_duplicate_vertices_still_valid_after_dedupe():
    geom = _rect_polygon(21.1, 44.8, 80.0, 60.0)
    ring = geom["coordinates"][0]
    # Insert duplicate consecutive vertex
    ring.insert(1, list(ring[0]))
    metrics = polygon_metrics(geom)
    assert metrics["area_m2"] > 0


def test_missing_coordinates_rejected():
    with pytest.raises(MapEditorGeometryError):
        validate_editor_boundary({"type": "Polygon", "coordinates": []})


def test_point_in_polygon_and_self_intersection_helpers():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert point_in_polygon((5.0, 5.0), square)
    assert not point_in_polygon((15.0, 5.0), square)
    bow = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    assert has_self_intersection(bow)


def test_place_points_on_segment_spacing():
    pts = place_points_on_segment((0.0, 0.0), (20.0, 0.0), spacing_m=5.0, start_offset_m=0.0, end_offset_m=0.0)
    assert len(pts) == 5  # 0,5,10,15,20
    assert pts[0] == (0.0, 0.0)
    assert abs(pts[-1][0] - 20.0) < 1e-6


def test_rows_clipped_to_rectangle():
    geom = _rect_polygon(21.1, 44.8, 90.0, 60.0)
    result = generate_planting_layout(
        geom,
        orientation_deg=0.0,  # east-west rows
        row_spacing_m=6.0,
        tree_spacing_m=5.0,
        first_row_offset_m=3.0,
        tree_start_offset_m=2.5,
        row_end_offset_m=2.5,
    )
    assert result["summary"]["row_count"] >= 5
    assert result["summary"]["tree_count"] > 0
    # All tree points inside bbox lon/lat roughly
    for tree in result["trees"]:
        assert 21.1 <= tree["longitude"] <= 21.102
        assert 44.8 <= tree["latitude"] <= 44.801


def test_rows_respect_spacing_approximately():
    geom = _rect_polygon(21.12, 44.81, 100.0, 80.0)
    result = generate_planting_layout(
        geom,
        orientation_deg=90.0,  # north-south rows
        row_spacing_m=5.0,
        tree_spacing_m=4.0,
        first_row_offset_m=2.5,
    )
    assert result["summary"]["row_count"] >= 8
    assert not result["warnings"] or result["summary"]["tree_count"] > 0


def test_concave_polygon_multiple_segments():
    # C-shaped concave polygon (meters ~)
    lon0, lat0 = 21.15, 44.85
    m_lat = 111_320.0
    m_lon = 111_320.0 * math.cos(math.radians(lat0))

    def ll(x_m: float, y_m: float) -> list[float]:
        return [lon0 + x_m / m_lon, lat0 + y_m / m_lat]

    # Outer C: thick C opening to the east
    coords = [
        ll(0, 0),
        ll(100, 0),
        ll(100, 30),
        ll(30, 30),
        ll(30, 70),
        ll(100, 70),
        ll(100, 100),
        ll(0, 100),
        ll(0, 0),
    ]
    geom = {"type": "Polygon", "coordinates": [coords]}
    result = generate_planting_layout(
        geom,
        orientation_deg=0.0,
        row_spacing_m=10.0,
        tree_spacing_m=8.0,
        first_row_offset_m=5.0,
    )
    # At least one logical row should have multiple segments in the middle band
    assert result["summary"]["segment_count"] >= result["summary"]["row_count"]
    assert result["summary"]["tree_count"] > 0


def test_too_narrow_warns():
    geom = _rect_polygon(21.2, 44.9, 6.0, 6.0)
    result = generate_planting_layout(
        geom,
        orientation_deg=0.0,
        row_spacing_m=20.0,
        tree_spacing_m=10.0,
        first_row_offset_m=15.0,
    )
    assert result["summary"]["row_count"] == 0
    assert result["warnings"]


def test_stable_row_numbering():
    geom = _rect_polygon(21.11, 44.82, 70.0, 50.0)
    a = generate_planting_layout(geom, orientation_deg=0, row_spacing_m=5, tree_spacing_m=4, first_row_offset_m=2)
    b = generate_planting_layout(geom, orientation_deg=0, row_spacing_m=5, tree_spacing_m=4, first_row_offset_m=2)
    assert [r["row_number"] for r in a["rows"]] == [r["row_number"] for r in b["rows"]]
    assert a["summary"]["tree_count"] == b["summary"]["tree_count"]


def test_rows_start_from_selected_edge_side():
    """First row must sit near the chosen reference edge, not the opposite side."""
    lon0, lat0 = 21.13, 44.83
    geom = _rect_polygon(lon0, lat0, 80.0, 60.0)
    # Ring: 0 south, 1 east, 2 north, 3 west (CCW)
    # Vertical west edge (index 3) → N-S rows; first row near west (smaller lon).
    west = generate_planting_layout(
        geom,
        orientation_deg=90.0,
        orientation_edge_index=3,
        row_spacing_m=5.0,
        tree_spacing_m=4.0,
        first_row_offset_m=2.0,
        last_row_offset_m=2.0,
        target_row_count=8,
    )
    # Vertical east edge (index 1) → first row near east (larger lon).
    east = generate_planting_layout(
        geom,
        orientation_deg=90.0,
        orientation_edge_index=1,
        row_spacing_m=5.0,
        tree_spacing_m=4.0,
        first_row_offset_m=2.0,
        last_row_offset_m=2.0,
        target_row_count=8,
    )
    assert west["summary"]["row_count"] >= 3
    assert east["summary"]["row_count"] >= 3

    def mean_lon_for_row(result: dict, row_number: int) -> float:
        pts = [t["longitude"] for t in result["trees"] if t["row_number"] == row_number]
        assert pts
        return sum(pts) / len(pts)

    west_first = mean_lon_for_row(west, min(t["row_number"] for t in west["trees"]))
    east_first = mean_lon_for_row(east, min(t["row_number"] for t in east["trees"]))
    # West-started first row is west of east-started first row.
    assert west_first < east_first
    # And they should be on opposite halves of the parcel.
    mid = lon0 + (80.0 / (111_320.0 * math.cos(math.radians(lat0)))) / 2.0
    assert west_first < mid
    assert east_first > mid
