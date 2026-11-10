"""Map satellite grid zones to orchard tree public IDs."""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.satellite.zones import parcel_bbox, point_in_geometry

_ZONE_KEY_RE = re.compile(r"\br(\d+)c(\d+)\b", re.IGNORECASE)


def trees_in_zone_geometry(
    geometry: dict[str, Any] | None,
    trees: Sequence[Any],
    *,
    parcel_boundary: dict[str, Any] | None = None,
    limit: int = 40,
) -> list[str]:
    """Return public_ids of trees whose position falls inside the zone polygon."""
    if not geometry or not trees:
        return []
    positions = _tree_positions(trees, parcel_boundary=parcel_boundary)
    if not positions:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for public_id, lon, lat in positions:
        if public_id in seen:
            continue
        if not point_in_geometry((lon, lat), geometry):
            continue
        seen.add(public_id)
        found.append(public_id)
        if len(found) >= limit:
            break
    return found


def trees_for_zone_keys(
    *,
    zone_keys: Sequence[str],
    zones: Sequence[Any],
    trees: Sequence[Any],
    parcel_boundary: dict[str, Any] | None = None,
    limit_per_zone: int = 20,
    total_limit: int = 60,
) -> list[str]:
    """Unique tree public_ids across the given zone keys (order preserved)."""
    zone_by_key = {
        str(getattr(zone, "zone_key", None) or "").lower(): zone
        for zone in zones
        if getattr(zone, "zone_key", None)
    }
    out: list[str] = []
    seen: set[str] = set()
    for key in zone_keys:
        zone = zone_by_key.get(str(key).lower())
        if zone is None:
            continue
        geometry = getattr(zone, "geometry", None)
        if not isinstance(geometry, dict):
            continue
        for public_id in trees_in_zone_geometry(
            geometry,
            trees,
            parcel_boundary=parcel_boundary,
            limit=limit_per_zone,
        ):
            if public_id in seen:
                continue
            seen.add(public_id)
            out.append(public_id)
            if len(out) >= total_limit:
                return out
    return out


def zone_tree_map(
    zones: Sequence[Any],
    trees: Sequence[Any],
    *,
    parcel_boundary: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for zone in zones:
        key = getattr(zone, "zone_key", None)
        if not key:
            continue
        geometry = getattr(zone, "geometry", None)
        mapping[str(key).lower()] = trees_in_zone_geometry(
            geometry if isinstance(geometry, dict) else None,
            trees,
            parcel_boundary=parcel_boundary,
        )
    return mapping


def format_tree_ids_label(tree_ids: Sequence[str], *, max_show: int = 8) -> str | None:
    if not tree_ids:
        return None
    shown = list(tree_ids[:max_show])
    extra = len(tree_ids) - len(shown)
    label = ", ".join(shown)
    if extra > 0:
        label = f"{label} (+{extra})"
    return label


def rewrite_zone_keys_in_text(
    text: str,
    zone_to_trees: dict[str, list[str]],
    *,
    fallback_trees: Sequence[str] | None = None,
) -> str:
    """Replace internal r3c0 keys with tree public IDs for farmer-facing copy."""
    if not text:
        return text
    all_trees = list(fallback_trees or [])

    def repl(match: re.Match[str]) -> str:
        key = f"r{match.group(1)}c{match.group(2)}".lower()
        trees = zone_to_trees.get(key) or []
        if trees:
            if len(trees) == 1:
                return trees[0]
            return f"{trees[0]} (+{len(trees) - 1})"
        if all_trees:
            return format_tree_ids_label(all_trees, max_show=3) or "deo parcele"
        return "deo parcele"

    return _ZONE_KEY_RE.sub(repl, text)


def rewrite_zone_keys_in_strings(
    values: Sequence[str],
    zone_to_trees: dict[str, list[str]],
    *,
    fallback_trees: Sequence[str] | None = None,
) -> list[str]:
    return [
        rewrite_zone_keys_in_text(item, zone_to_trees, fallback_trees=fallback_trees)
        for item in values
    ]


def _tree_positions(
    trees: Sequence[Any],
    *,
    parcel_boundary: dict[str, Any] | None,
) -> list[tuple[str, float, float]]:
    """Resolve (public_id, lon, lat) using GPS when present, else schematic → bbox."""
    direct: list[tuple[str, float, float]] = []
    schematic: list[tuple[str, float, float]] = []
    for tree in trees:
        public_id = getattr(tree, "public_id", None)
        if not public_id:
            continue
        lon = _float_or_none(getattr(tree, "longitude", None))
        lat = _float_or_none(getattr(tree, "latitude", None))
        if lon is not None and lat is not None:
            direct.append((str(public_id), lon, lat))
            continue
        nx = _float_or_none(getattr(tree, "normalized_x", None))
        ny = _float_or_none(getattr(tree, "normalized_y", None))
        if nx is not None and ny is not None:
            schematic.append((str(public_id), nx, ny))

    if direct:
        return direct
    if not schematic or not parcel_boundary:
        return []
    try:
        west, south, east, north = parcel_bbox(parcel_boundary)
    except ValueError:
        return []
    max_x = max(nx for _, nx, _ in schematic) or 1.0
    max_y = max(ny for _, _, ny in schematic) or 1.0
    if max_x <= 0 or max_y <= 0:
        return []
    width = east - west
    height = north - south
    if width <= 0 or height <= 0:
        return []
    out: list[tuple[str, float, float]] = []
    for public_id, nx, ny in schematic:
        # Layout y grows with row number; satellite row 0 is south → map y from south.
        lon = west + (nx / max_x) * width
        lat = south + (ny / max_y) * height
        out.append((public_id, lon, lat))
    return out


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
