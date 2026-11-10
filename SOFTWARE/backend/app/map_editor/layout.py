"""Generate orchard rows and trees clipped to an irregular parcel polygon."""

from __future__ import annotations

import math
from typing import Any

from app.map_editor.geometry import (
    line_polygon_segments,
    place_points_on_segment,
    point_in_polygon,
    suggested_orientation_deg,
)
from app.map_editor.metrics import polygon_metrics
from app.map_editor.validation import MapEditorGeometryError, ensure_valid_metric_ring, validate_editor_boundary


def generate_planting_layout(
    boundary: dict[str, Any],
    *,
    orientation_deg: float,
    row_spacing_m: float,
    tree_spacing_m: float,
    first_row_offset_m: float = 0.0,
    last_row_offset_m: float = 0.0,
    row_end_offset_m: float = 0.0,
    tree_start_offset_m: float | None = None,
    boundary_buffer_m: float = 0.0,
    target_row_count: int | None = None,
    start_row_number: int = 1,
    number_rows_ascending: bool = True,
    default_variety: str | None = None,
    default_planting_year: int | None = None,
    orientation_edge_index: int | None = None,
) -> dict[str, Any]:
    geometry = validate_editor_boundary(boundary)
    if row_spacing_m <= 0:
        raise MapEditorGeometryError("Razmak između redova mora biti veći od nula.", "row_spacing")
    if tree_spacing_m <= 0:
        raise MapEditorGeometryError("Razmak između stabala mora biti veći od nula.", "tree_spacing")
    if start_row_number < 1:
        raise MapEditorGeometryError("Početni broj reda mora biti najmanje 1.", "start_row")
    if target_row_count is not None and target_row_count < 1:
        raise MapEditorGeometryError("Broj redova mora biti najmanje 1.", "target_row_count")

    proj, ring = ensure_valid_metric_ring(geometry)
    metrics = polygon_metrics(geometry)
    suggestion = suggested_orientation_deg(ring)

    # Prefer explicit edge: angle from metric ring guarantees rows are parallel to that side.
    resolved_orientation = float(orientation_deg) % 180.0
    edge_mid: tuple[float, float] | None = None
    if orientation_edge_index is not None:
        n = len(ring)
        if n < 2:
            raise MapEditorGeometryError("Granica nema ivice za orijentaciju.", "orientation_edge")
        i = int(orientation_edge_index) % n
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        resolved_orientation = math.degrees(math.atan2(by - ay, bx - ax)) % 180.0
        edge_mid = ((ax + bx) / 2.0, (ay + by) / 2.0)

    angle = math.radians(resolved_orientation)
    # Row direction (along the row)
    dir_x, dir_y = math.cos(angle), math.sin(angle)
    # Perpendicular (row progression)
    perp_x, perp_y = -math.sin(angle), math.cos(angle)

    projections = [p[0] * perp_x + p[1] * perp_y for p in ring]
    p_min, p_max = min(projections), max(projections)
    extent = max(abs(p_max - p_min) * 2.0, 50.0) + 100.0

    start_offset = first_row_offset_m if first_row_offset_m > 0 else 0.0
    end_offset = last_row_offset_m if last_row_offset_m > 0 else 0.0
    tree_start = tree_spacing_m / 2.0 if tree_start_offset_m is None else max(0.0, tree_start_offset_m)
    tree_end = row_end_offset_m if row_end_offset_m > 0 else tree_start
    # Optional inward buffer from boundary for trees
    min_len = tree_start + tree_end + tree_spacing_m * 0.25

    rows_out: list[dict[str, Any]] = []
    trees_out: list[dict[str, Any]] = []
    warnings: list[str] = []

    # Start from the selected reference edge side (not always p_min).
    # Edge parallel to rows sits near p_min or p_max on the perpendicular axis.
    start_from_max = False
    if edge_mid is not None:
        edge_proj = edge_mid[0] * perp_x + edge_mid[1] * perp_y
        start_from_max = abs(edge_proj - p_max) < abs(edge_proj - p_min)

    if start_from_max:
        # First row near selected edge at p_max, progress toward p_min.
        cursor_start = p_max - start_offset
        limit = p_min + end_offset
        step_sign = -1.0
    else:
        # First row near selected edge at p_min (or default), progress toward p_max.
        cursor_start = p_min + start_offset
        if cursor_start < p_min:
            cursor_start = p_min
        limit = p_max - end_offset
        step_sign = 1.0

    if (step_sign < 0 and cursor_start < limit) or (step_sign > 0 and cursor_start > limit):
        warnings.append("Pomeraji od granica ostavljaju prostor van parcele — nema validnih redova.")
        return _empty_result(geometry, metrics, suggestion, resolved_orientation, warnings)

    available_span = abs(limit - cursor_start)
    effective_row_spacing = float(row_spacing_m)

    def _offsets_with_spacing(spacing: float) -> list[float]:
        out: list[float] = []
        cursor = cursor_start
        if step_sign < 0:
            while cursor >= limit - 1e-6:
                out.append(cursor)
                cursor -= spacing
                if target_row_count is not None and len(out) >= target_row_count:
                    break
        else:
            while cursor <= limit + 1e-6:
                out.append(cursor)
                cursor += spacing
                if target_row_count is not None and len(out) >= target_row_count:
                    break
        return out

    candidate_offsets = _offsets_with_spacing(effective_row_spacing)

    # If the farmer asked for N rows and fixed spacing doesn't fit, distribute
    # evenly across the usable width so the requested count is honored.
    min_auto_spacing = max(1.0, float(row_spacing_m) * 0.45)
    if (
        target_row_count is not None
        and target_row_count >= 2
        and len(candidate_offsets) < target_row_count
        and available_span > 1e-6
    ):
        even_spacing = available_span / float(target_row_count - 1)
        if even_spacing + 1e-9 >= min_auto_spacing:
            effective_row_spacing = even_spacing
            candidate_offsets = []
            for i in range(target_row_count):
                candidate_offsets.append(cursor_start + step_sign * even_spacing * i)
            warnings.append(
                f"Zatraženo {target_row_count} redova: razmak je automatski prilagođen "
                f"sa {row_spacing_m:g} m na {even_spacing:.2f} m da svi stanu u parcelu."
            )
        else:
            warnings.append(
                f"Zatraženo {target_row_count} redova, a sa razmakom {row_spacing_m:g} m "
                f"staje {len(candidate_offsets)}. Smanjite razmak ili margine "
                f"(za {target_row_count} redova treba ≈ {available_span / max(target_row_count - 1, 1):.2f} m)."
            )

    if not candidate_offsets:
        warnings.append("Uz zadati razmak i granicu nije moguće generisati redove.")
        return _empty_result(geometry, metrics, suggestion, resolved_orientation, warnings)

    logical_index = 0
    for offset in candidate_offsets:
        # Point on the perpendicular axis at this offset, through centroid
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        # Move from a point on the mean projection to this offset
        mean_p = cx * perp_x + cy * perp_y
        origin = (
            cx + (offset - mean_p) * perp_x,
            cy + (offset - mean_p) * perp_y,
        )
        segments = line_polygon_segments(origin, (dir_x, dir_y), ring, extent=extent)
        if not segments:
            continue

        # Multi-segment: same logical row number, distinct segment_index
        # Documented: concave parcels may produce multiple segments for one candidate line;
        # they share row_number but have separate geometries (not connected outside parcel).
        row_number = start_row_number + logical_index
        if not number_rows_ascending:
            # Will renumber after collecting
            row_number = logical_index  # temporary
        segment_kept = 0
        for seg_i, (a, b) in enumerate(segments):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            if length < min_len:
                continue
            points_xy = place_points_on_segment(
                a,
                b,
                spacing_m=tree_spacing_m,
                start_offset_m=tree_start,
                end_offset_m=tree_end,
            )
            # Filter by buffer / inside
            kept_points: list[tuple[float, float]] = []
            for pt in points_xy:
                if boundary_buffer_m > 0 and not _inside_with_buffer(pt, ring, boundary_buffer_m):
                    continue
                if not point_in_polygon(pt, ring):
                    continue
                kept_points.append(pt)
            if not kept_points and length >= min_len:
                # Still keep empty row segment? Skip if no trees
                continue

            a_ll = proj.to_lonlat(*a)
            b_ll = proj.to_lonlat(*b)
            row_id = f"draft-r{logical_index + 1}-s{segment_kept + 1}"
            rows_out.append(
                {
                    "draft_id": row_id,
                    "row_number": row_number,
                    "segment_index": segment_kept,
                    "length_m": round(length, 2),
                    "tree_count": len(kept_points),
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[a_ll[0], a_ll[1]], [b_ll[0], b_ll[1]]],
                    },
                    "default_variety": default_variety,
                    "default_planting_year": default_planting_year,
                }
            )
            for ti, pt in enumerate(kept_points):
                lon, lat = proj.to_lonlat(*pt)
                trees_out.append(
                    {
                        "draft_id": f"draft-t-{row_id}-{ti + 1}",
                        "row_draft_id": row_id,
                        "row_number": row_number,
                        "tree_number": ti + 1,
                        "latitude": lat,
                        "longitude": lon,
                        "variety": default_variety,
                        "planting_year": default_planting_year,
                        "inherited_variety": True,
                        "manually_placed": False,
                    }
                )
            segment_kept += 1

        if segment_kept > 0:
            logical_index += 1

    if not number_rows_ascending and rows_out:
        max_idx = max(r["row_number"] for r in rows_out)
        # temporary indices were 0..n-1
        for r in rows_out:
            r["row_number"] = start_row_number + (max_idx - r["row_number"])
        for t in trees_out:
            t["row_number"] = start_row_number + (max_idx - t["row_number"])

    if not rows_out:
        warnings.append(
            "Nije moguće generisati redove unutar granice sa zadatim razmakom i pomerajima."
        )

    total_trees = len(trees_out)
    per_row: dict[int, int] = {}
    for t in trees_out:
        per_row[t["row_number"]] = per_row.get(t["row_number"], 0) + 1

    return {
        "boundary": geometry,
        "metrics": metrics,
        "suggested_orientation_deg": round(suggestion, 2),
        "config": {
            "orientation_deg": resolved_orientation,
            "orientation_edge_index": orientation_edge_index,
            "row_spacing_m": round(effective_row_spacing, 4),
            "tree_spacing_m": tree_spacing_m,
            "first_row_offset_m": first_row_offset_m,
            "last_row_offset_m": last_row_offset_m,
            "row_end_offset_m": row_end_offset_m,
            "tree_start_offset_m": tree_start,
            "boundary_buffer_m": boundary_buffer_m,
            "target_row_count": target_row_count,
            "start_row_number": start_row_number,
            "number_rows_ascending": number_rows_ascending,
            "default_variety": default_variety,
            "default_planting_year": default_planting_year,
        },
        "rows": rows_out,
        "trees": trees_out,
        "summary": {
            "row_count": len({r["row_number"] for r in rows_out}),
            "segment_count": len(rows_out),
            "tree_count": total_trees,
            "trees_per_row": per_row,
            "average_trees_per_row": round(total_trees / max(len(per_row), 1), 2) if per_row else 0.0,
        },
        "warnings": warnings,
        "notes": [
            "Za konkavne parcele jedna kandidat linija može dati više segmenata; "
            "segmenti dele broj reda ali nisu povezani kroz prostor van parcele.",
            "Razmaci i sečenje računaju se u lokalnoj metričkoj projekciji oko parcele (WGS84 skladište).",
        ],
    }


def _inside_with_buffer(point: tuple[float, float], ring: list[tuple[float, float]], buffer_m: float) -> bool:
    """Approximate: point must be inside and at least buffer_m from each edge."""
    if not point_in_polygon(point, ring):
        return False
    if buffer_m <= 0:
        return True
    n = len(ring)
    px, py = point
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        dist = _dist_point_to_segment(px, py, ax, ay, bx, by)
        if dist < buffer_m:
            return False
    return True


def _dist_point_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))
    cx, cy = ax + t * abx, ay + t * aby
    return math.hypot(px - cx, py - cy)


def _empty_result(
    geometry: dict[str, Any],
    metrics: dict[str, Any],
    suggestion: float,
    orientation_deg: float,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "boundary": geometry,
        "metrics": metrics,
        "suggested_orientation_deg": round(suggestion, 2),
        "config": {"orientation_deg": float(orientation_deg) % 180.0},
        "rows": [],
        "trees": [],
        "summary": {
            "row_count": 0,
            "segment_count": 0,
            "tree_count": 0,
            "trees_per_row": {},
            "average_trees_per_row": 0.0,
        },
        "warnings": warnings,
        "notes": [],
    }
