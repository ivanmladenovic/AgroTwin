"""Parcel boundary GeoJSON validation. Not satellite-specific."""

from __future__ import annotations

import math
from typing import Any

METERS_PER_DEGREE_LAT = 111_320.0
MAX_AREA_HA = 500.0


class InvalidParcelGeometry(ValueError):
    def __init__(self, message: str, code: str = "invalid_geometry") -> None:
        self.code = code
        super().__init__(message)


def validate_boundary_geojson(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidParcelGeometry("Granica parcele mora biti GeoJSON objekat.")
    geom_type = value.get("type")
    if geom_type == "Feature":
        return validate_boundary_geojson(value.get("geometry"))
    if geom_type == "FeatureCollection":
        features = value.get("features")
        if not isinstance(features, list) or not features:
            raise InvalidParcelGeometry("GeoJSON kolekcija granice je prazna.")
        return validate_boundary_geojson(features[0])
    if geom_type not in {"Polygon", "MultiPolygon"}:
        raise InvalidParcelGeometry("Granica parcele mora biti Polygon ili MultiPolygon.")
    coordinates = value.get("coordinates")
    if geom_type == "Polygon":
        _validate_polygon_coords(coordinates)
    else:
        if not isinstance(coordinates, list) or not coordinates:
            raise InvalidParcelGeometry("MultiPolygon mora imati bar jedan poligon.")
        for polygon in coordinates:
            _validate_polygon_coords(polygon)
    area = approximate_area_hectares({"type": geom_type, "coordinates": coordinates})
    if area is not None and area > MAX_AREA_HA:
        raise InvalidParcelGeometry("Granica parcele je veća od dozvoljenih 500 ha.")
    return {"type": geom_type, "coordinates": coordinates}


def approximate_area_hectares(geojson: dict[str, Any]) -> float | None:
    geom_type = geojson.get("type")
    if geom_type == "Polygon":
        rings = geojson.get("coordinates")
        if not isinstance(rings, list) or not rings:
            return None
        return abs(_ring_area_ha(rings[0]))
    if geom_type == "MultiPolygon":
        total = 0.0
        for polygon in geojson.get("coordinates") or []:
            if isinstance(polygon, list) and polygon:
                total += abs(_ring_area_ha(polygon[0]))
        return total
    return None


def _validate_polygon_coords(coordinates: object) -> None:
    if not isinstance(coordinates, list) or not coordinates:
        raise InvalidParcelGeometry("Polygon mora imati spoljni prsten.")
    ring = coordinates[0]
    if not isinstance(ring, list) or len(ring) < 4:
        raise InvalidParcelGeometry("Polygon mora imati bar 4 tačke, uključujući zatvaranje prstena.")
    positions = [_position(item) for item in ring]
    if positions[0] != positions[-1]:
        raise InvalidParcelGeometry("Polygon prsten mora biti zatvoren.")
    if len({(round(lon, 7), round(lat, 7)) for lon, lat in positions}) < 3:
        raise InvalidParcelGeometry("Polygon mora imati bar 3 različite tačke.")


def _position(value: object) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise InvalidParcelGeometry("Koordinata mora biti [longitude, latitude].")
    try:
        lon = float(value[0])
        lat = float(value[1])
    except (TypeError, ValueError) as exc:
        raise InvalidParcelGeometry("Koordinate granice nisu brojevi.") from exc
    if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 90 or abs(lon) > 180:
        raise InvalidParcelGeometry("Koordinate granice su van opsega.")
    return lon, lat


def _ring_area_ha(ring: list) -> float:
    positions = [_position(item) for item in ring]
    if len(positions) < 4:
        return 0.0
    lat0 = sum(lat for _, lat in positions[:-1]) / max(len(positions) - 1, 1)
    scale_x = METERS_PER_DEGREE_LAT * max(math.cos(math.radians(lat0)), 0.2)
    scale_y = METERS_PER_DEGREE_LAT
    area = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(positions, positions[1:], strict=False):
        x1, y1 = lon1 * scale_x, lat1 * scale_y
        x2, y2 = lon2 * scale_x, lat2 * scale_y
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 10_000.0
