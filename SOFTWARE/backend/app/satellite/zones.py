"""Regular grid zoning over a parcel polygon (MVP, no external GIS deps)."""

from __future__ import annotations

import math
from typing import Any


def parcel_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    coords = list(_iter_coords(geometry))
    if not coords:
        raise ValueError("Parcel geometry has no coordinates")
    lons = [lon for lon, _ in coords]
    lats = [lat for _, lat in coords]
    return min(lons), min(lats), max(lons), max(lats)


def expand_polygon_meters(geometry: dict[str, Any], meters: float = 12.0) -> dict[str, Any]:
    """Push polygon vertices outward from the centroid by ~meters.

    Used only for visualization sampling so edge pixels near the true boundary
    are not left empty; the map still clips to the exact parcel outline.
    """
    if meters <= 0:
        return geometry
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        rings = geometry.get("coordinates") or []
        if not rings:
            return geometry
        return {
            "type": "Polygon",
            "coordinates": [_expand_ring_meters(rings[0], meters), *rings[1:]],
        }
    if geom_type == "MultiPolygon":
        polys = geometry.get("coordinates") or []
        expanded = []
        for polygon in polys:
            if not polygon:
                continue
            expanded.append([_expand_ring_meters(polygon[0], meters), *polygon[1:]])
        if not expanded:
            return geometry
        return {"type": "MultiPolygon", "coordinates": expanded}
    return geometry


def _expand_ring_meters(ring: list, meters: float) -> list[list[float]]:
    if not isinstance(ring, list) or len(ring) < 4:
        return ring
    positions: list[tuple[float, float]] = []
    for item in ring:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        positions.append((float(item[0]), float(item[1])))
    if len(positions) < 4:
        return ring
    # Exclude closing vertex for centroid.
    core = positions[:-1] if positions[0] == positions[-1] else positions
    if not core:
        return ring
    cx = sum(lon for lon, _ in core) / len(core)
    cy = sum(lat for _, lat in core) / len(core)
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = meters_per_deg_lat * max(math.cos(math.radians(cy)), 0.2)
    out: list[list[float]] = []
    for lon, lat in core:
        vx, vy = lon - cx, lat - cy
        mx = vx * meters_per_deg_lon
        my = vy * meters_per_deg_lat
        length = math.hypot(mx, my)
        if length < 1e-9:
            out.append([lon, lat])
            continue
        ux, uy = mx / length, my / length
        out.append(
            [
                lon + (ux * meters) / meters_per_deg_lon,
                lat + (uy * meters) / meters_per_deg_lat,
            ]
        )
    if out and out[0] != out[-1]:
        out.append([out[0][0], out[0][1]])
    return out


def build_zone_grid(
    geometry: dict[str, Any],
    *,
    grid_size: int = 4,
) -> list[tuple[str, dict[str, Any]]]:
    """Divide the parcel bounding box into an N×N grid; keep cells that intersect the parcel.

    Intersection is approximate (cell center inside polygon or cell overlaps bbox of rings).
    """
    if grid_size < 1 or grid_size > 32:
        raise ValueError("grid_size must be between 1 and 32")
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
    if max_lon <= min_lon or max_lat <= min_lat:
        raise ValueError("Invalid parcel bounding box")
    dx = (max_lon - min_lon) / grid_size
    dy = (max_lat - min_lat) / grid_size
    zones: list[tuple[str, dict[str, Any]]] = []
    for row in range(grid_size):
        for col in range(grid_size):
            west = min_lon + col * dx
            east = west + dx
            south = min_lat + row * dy
            north = south + dy
            cell = _rectangle(west, south, east, north)
            center = ((west + east) / 2.0, (south + north) / 2.0)
            if _point_in_geometry(center, geometry) or _cell_overlaps_geometry(cell, geometry):
                zones.append((f"r{row}c{col}", cell))
    if not zones:
        # Degenerate tiny parcels: fall back to the full geometry as one zone.
        zones.append(("r0c0", geometry))
    return zones


def _rectangle(west: float, south: float, east: float, north: float) -> dict[str, Any]:
    ring = [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def _iter_coords(geometry: dict[str, Any]):
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geom_type == "Polygon" and isinstance(coordinates, list):
        for ring in coordinates:
            for point in ring:
                yield float(point[0]), float(point[1])
    elif geom_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            for ring in polygon:
                for point in ring:
                    yield float(point[0]), float(point[1])


def point_in_geometry(point: tuple[float, float], geometry: dict[str, Any]) -> bool:
    """Public wrapper: (lon, lat) inside GeoJSON Polygon/MultiPolygon."""
    return _point_in_geometry(point, geometry)


def _point_in_geometry(point: tuple[float, float], geometry: dict[str, Any]) -> bool:
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        rings = geometry.get("coordinates") or []
        if not rings:
            return False
        if not _point_in_ring(point, rings[0]):
            return False
        for hole in rings[1:]:
            if _point_in_ring(point, hole):
                return False
        return True
    if geom_type == "MultiPolygon":
        for polygon in geometry.get("coordinates") or []:
            if _point_in_geometry(point, {"type": "Polygon", "coordinates": polygon}):
                return True
    return False


def _point_in_ring(point: tuple[float, float], ring: list) -> bool:
    """Ray casting."""
    x, y = point
    inside = False
    n = len(ring)
    if n < 4:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def _cell_overlaps_geometry(cell: dict[str, Any], geometry: dict[str, Any]) -> bool:
    # Conservative: any cell corner inside, or parcel point inside cell.
    for lon, lat in _iter_coords(cell):
        if _point_in_geometry((lon, lat), geometry):
            return True
    cell_bbox = parcel_bbox(cell)
    for lon, lat in _iter_coords(geometry):
        if cell_bbox[0] <= lon <= cell_bbox[2] and cell_bbox[1] <= lat <= cell_bbox[3]:
            if _point_in_geometry((lon, lat), cell):
                return True
    # Also check if extents overlap and centers are close (tiny parcels).
    g_bbox = parcel_bbox(geometry)
    return not (
        cell_bbox[2] < g_bbox[0]
        or cell_bbox[0] > g_bbox[2]
        or cell_bbox[3] < g_bbox[1]
        or cell_bbox[1] > g_bbox[3]
    ) and math.hypot(
        (cell_bbox[0] + cell_bbox[2]) / 2 - (g_bbox[0] + g_bbox[2]) / 2,
        (cell_bbox[1] + cell_bbox[3]) / 2 - (g_bbox[1] + g_bbox[3]) / 2,
    ) < max(g_bbox[2] - g_bbox[0], g_bbox[3] - g_bbox[1], 1e-6)
