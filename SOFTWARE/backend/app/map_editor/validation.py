"""Boundary validation for the map editor (Serbian messages)."""

from __future__ import annotations

from typing import Any

from app.core.geojson import InvalidParcelGeometry, validate_boundary_geojson
from app.map_editor.geometry import (
    dedupe_consecutive,
    has_self_intersection,
    polygon_area,
    ring_from_lonlat,
)
from app.map_editor.metrics import polygon_metrics
from app.map_editor.projection import LocalMetricProjection


class MapEditorGeometryError(ValueError):
    def __init__(self, message: str, code: str = "invalid_geometry") -> None:
        self.code = code
        super().__init__(message)


def validate_editor_boundary(value: object) -> dict[str, Any]:
    """Validate GeoJSON polygon for map editor use (stricter than satellite-only checks)."""
    try:
        geometry = validate_boundary_geojson(value)
    except InvalidParcelGeometry as exc:
        raise MapEditorGeometryError(str(exc), getattr(exc, "code", "invalid_geometry")) from exc

    metrics = polygon_metrics(geometry)
    if metrics["vertex_count"] < 3:
        raise MapEditorGeometryError(
            "Poligon mora imati najmanje tri različita temena.",
            "too_few_vertices",
        )
    if metrics["self_intersecting"]:
        raise MapEditorGeometryError(
            "Poligon se seče sam sa sobom. Ispravite granicu pre čuvanja.",
            "self_intersection",
        )
    if metrics["area_m2"] <= 0:
        raise MapEditorGeometryError(
            "Površina poligona mora biti veća od nule.",
            "zero_area",
        )

    # Duplicate consecutive vertices already handled in metrics; re-check lon/lat ranges
    coords = geometry["coordinates"][0] if geometry["type"] == "Polygon" else geometry["coordinates"][0][0]
    for pair in coords:
        lon, lat = float(pair[0]), float(pair[1])
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise MapEditorGeometryError(
                "Koordinate su van dozvoljenog opsega (WGS84).",
                "out_of_range",
            )

    return geometry


def ensure_valid_metric_ring(geometry: dict[str, Any]) -> tuple[LocalMetricProjection, list[tuple[float, float]]]:
    metrics = polygon_metrics(geometry)
    origin_lon = metrics["origin_lon"]
    origin_lat = metrics["origin_lat"]
    if origin_lon is None or origin_lat is None:
        raise MapEditorGeometryError("Nije moguće odrediti projekciju za poligon.", "no_origin")
    proj = LocalMetricProjection.from_lonlat(origin_lon, origin_lat)
    outer = geometry["coordinates"][0] if geometry["type"] == "Polygon" else geometry["coordinates"][0][0]
    ring = dedupe_consecutive(ring_from_lonlat(outer, proj.to_xy))
    if abs(polygon_area(ring)) <= 0:
        raise MapEditorGeometryError("Površina poligona mora biti veća od nule.", "zero_area")
    if has_self_intersection(ring):
        raise MapEditorGeometryError(
            "Poligon se seče sam sa sobom. Ispravite granicu pre čuvanja.",
            "self_intersection",
        )
    return proj, ring
