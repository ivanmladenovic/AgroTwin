"""Metric area / perimeter for WGS84 GeoJSON polygons (local equirectangular)."""

from __future__ import annotations

from typing import Any

from app.map_editor.geometry import (
    dedupe_consecutive,
    edge_lengths,
    has_self_intersection,
    polygon_area,
    polygon_perimeter,
    ring_from_lonlat,
)
from app.map_editor.projection import LocalMetricProjection


def _extract_outer_ring(geometry: dict[str, Any]) -> list[list[float]]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if geom_type == "Feature":
        return _extract_outer_ring(geometry.get("geometry") or {})
    if geom_type == "Polygon":
        if not isinstance(coords, list) or not coords:
            return []
        return coords[0]
    if geom_type == "MultiPolygon":
        if not isinstance(coords, list) or not coords:
            return []
        first = coords[0]
        if not isinstance(first, list) or not first:
            return []
        return first[0]
    return []


def polygon_metrics(geometry: dict[str, Any]) -> dict[str, Any]:
    outer = _extract_outer_ring(geometry)
    if len(outer) < 3:
        return {
            "area_m2": 0.0,
            "area_ha": 0.0,
            "perimeter_m": 0.0,
            "vertex_count": 0,
            "edge_lengths_m": [],
            "self_intersecting": False,
            "origin_lon": None,
            "origin_lat": None,
        }

    # Origin = ring centroid (lon/lat average of unique vertices)
    lons = [float(p[0]) for p in outer if len(p) >= 2]
    lats = [float(p[1]) for p in outer if len(p) >= 2]
    if outer and outer[0] == outer[-1] and len(lons) > 1:
        lons = lons[:-1]
        lats = lats[:-1]
    origin_lon = sum(lons) / len(lons)
    origin_lat = sum(lats) / len(lats)
    proj = LocalMetricProjection.from_lonlat(origin_lon, origin_lat)
    ring = dedupe_consecutive(ring_from_lonlat(outer, proj.to_xy))
    area = abs(polygon_area(ring))
    return {
        "area_m2": round(area, 2),
        "area_ha": round(area / 10_000.0, 4),
        "perimeter_m": round(polygon_perimeter(ring), 2),
        "vertex_count": len(ring),
        "edge_lengths_m": [round(v, 2) for v in edge_lengths(ring)],
        "self_intersecting": has_self_intersection(ring),
        "origin_lon": origin_lon,
        "origin_lat": origin_lat,
    }
