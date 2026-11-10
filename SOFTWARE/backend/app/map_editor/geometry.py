"""2D geometry helpers in local metric coordinates."""

from __future__ import annotations

import math
from typing import Sequence


Point = tuple[float, float]
Ring = list[Point]
Segment = tuple[Point, Point]


def ring_from_lonlat(
    coords: Sequence[Sequence[float]],
    to_xy,
) -> Ring:
    ring: Ring = []
    for pair in coords:
        if len(pair) < 2:
            continue
        ring.append(to_xy(float(pair[0]), float(pair[1])))
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def close_ring(ring: Ring) -> Ring:
    if not ring:
        return []
    if ring[0] == ring[-1]:
        return list(ring)
    return list(ring) + [ring[0]]


def polygon_area(ring: Ring) -> float:
    """Signed area (m²). Positive for CCW."""
    if len(ring) < 3:
        return 0.0
    closed = close_ring(ring)
    total = 0.0
    for i in range(len(closed) - 1):
        x1, y1 = closed[i]
        x2, y2 = closed[i + 1]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def polygon_perimeter(ring: Ring) -> float:
    if len(ring) < 2:
        return 0.0
    closed = close_ring(ring)
    total = 0.0
    for i in range(len(closed) - 1):
        x1, y1 = closed[i]
        x2, y2 = closed[i + 1]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def edge_lengths(ring: Ring) -> list[float]:
    if len(ring) < 2:
        return []
    closed = close_ring(ring)
    lengths: list[float] = []
    for i in range(len(closed) - 1):
        x1, y1 = closed[i]
        x2, y2 = closed[i + 1]
        lengths.append(math.hypot(x2 - x1, y2 - y1))
    return lengths


def point_in_polygon(point: Point, ring: Ring) -> bool:
    """Ray casting; boundary counts as inside."""
    if len(ring) < 3:
        return False
    x, y = point
    closed = close_ring(ring)
    inside = False
    for i in range(len(closed) - 1):
        x1, y1 = closed[i]
        x2, y2 = closed[i + 1]
        if _point_on_segment(point, (x1, y1), (x2, y2), tol=1e-6):
            return True
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x_int >= x - 1e-9:
                inside = not inside
    return inside


def _point_on_segment(p: Point, a: Point, b: Point, *, tol: float = 1e-6) -> bool:
    ax, ay = a
    bx, by = b
    px, py = p
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > tol * max(1.0, math.hypot(bx - ax, by - ay)):
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    if dot < -tol:
        return False
    len_sq = (bx - ax) ** 2 + (by - ay) ** 2
    if dot - len_sq > tol:
        return False
    return True


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Proper intersection (shared endpoints of adjacent edges are ignored by caller)."""

    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 == 0 and o2 == 0 and o3 == 0 and o4 == 0:
        # Collinear overlap — treat as self-intersection if ranges overlap interiorly
        return _collinear_overlap(a, b, c, d)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _collinear_overlap(a: Point, b: Point, c: Point, d: Point) -> bool:
    def project(p: Point) -> float:
        return p[0] + p[1] * 1_000.0

    a0, a1 = sorted((project(a), project(b)))
    b0, b1 = sorted((project(c), project(d)))
    return a0 < b1 - 1e-9 and b0 < a1 - 1e-9


def has_self_intersection(ring: Ring) -> bool:
    n = len(ring)
    if n < 4:
        return False
    edges = [(ring[i], ring[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            # Skip adjacent edges (including first/last)
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            if _segments_intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return True
    return False


def dedupe_consecutive(ring: Ring, *, tol: float = 1e-6) -> Ring:
    if not ring:
        return []
    out: Ring = [ring[0]]
    for p in ring[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > tol:
            out.append(p)
    if len(out) >= 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= tol:
        out = out[:-1]
    return out


def line_polygon_segments(
    origin: Point,
    direction: Point,
    ring: Ring,
    *,
    extent: float,
) -> list[Segment]:
    """Intersect an infinite line with a polygon; return interior segments."""
    if len(ring) < 3:
        return []
    dx, dy = direction
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return []
    ux, uy = dx / length, dy / length
    ox, oy = origin

    # Parameterize line as P(t) = origin + t * unit
    hits: list[float] = []
    closed = close_ring(ring)
    for i in range(len(closed) - 1):
        a = closed[i]
        b = closed[i + 1]
        t = _line_edge_intersection_t(ox, oy, ux, uy, a, b)
        if t is not None:
            hits.append(t)

    # Also include vertices that lie on the line
    for p in ring:
        vx, vy = p[0] - ox, p[1] - oy
        # Distance to line
        cross = abs(vx * uy - vy * ux)
        if cross <= 1e-4:
            hits.append(vx * ux + vy * uy)

    if not hits:
        return []

    # Expand slightly beyond polygon to ensure coverage, then clip by inside tests
    t_min = min(hits) - 1.0
    t_max = max(hits) + 1.0
    # Sample densely along [t_min, t_max] is expensive; use sorted unique hits
    uniq = sorted(set(round(t, 6) for t in hits))
    if len(uniq) < 2:
        # Degenerate — try bounding box extremes
        bbox = _bbox(ring)
        corners = [
            (bbox[0], bbox[1]),
            (bbox[2], bbox[1]),
            (bbox[2], bbox[3]),
            (bbox[0], bbox[3]),
        ]
        for c in corners:
            vx, vy = c[0] - ox, c[1] - oy
            uniq.append(vx * ux + vy * uy)
        uniq = sorted(set(round(t, 6) for t in uniq))

    # Pad with extent ends
    uniq = sorted(set(uniq + [t_min, t_max, -extent, extent]))

    segments: list[Segment] = []
    for i in range(len(uniq) - 1):
        t0, t1 = uniq[i], uniq[i + 1]
        if t1 - t0 < 1e-4:
            continue
        mid_t = (t0 + t1) / 2.0
        mid = (ox + ux * mid_t, oy + uy * mid_t)
        if point_in_polygon(mid, ring):
            p0 = (ox + ux * t0, oy + uy * t0)
            p1 = (ox + ux * t1, oy + uy * t1)
            # Clamp endpoints to polygon boundary by walking if needed
            segments.append((p0, p1))

    return _merge_collinear_segments(segments)


def _line_edge_intersection_t(
    ox: float,
    oy: float,
    ux: float,
    uy: float,
    a: Point,
    b: Point,
) -> float | None:
    """Intersection of line origin+t*unit with segment ab. Returns t or None."""
    ax, ay = a
    bx, by = b
    ex, ey = bx - ax, by - ay
    denom = ux * ey - uy * ex
    if abs(denom) < 1e-12:
        return None
    dx, dy = ax - ox, ay - oy
    t = (dx * ey - dy * ex) / denom
    u = (dx * uy - dy * ux) / denom
    if -1e-9 <= u <= 1.0 + 1e-9:
        return t
    return None


def _bbox(ring: Ring) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _merge_collinear_segments(segments: list[Segment], *, gap: float = 0.05) -> list[Segment]:
    if not segments:
        return []
    # Sort by start projection along first segment direction
    def key(seg: Segment) -> float:
        return seg[0][0] + seg[0][1] * 1000.0

    ordered = sorted(segments, key=key)
    merged: list[Segment] = [ordered[0]]
    for seg in ordered[1:]:
        last = merged[-1]
        if math.hypot(seg[0][0] - last[1][0], seg[0][1] - last[1][1]) <= gap:
            merged[-1] = (last[0], seg[1])
        else:
            merged.append(seg)
    return merged


def place_points_on_segment(
    start: Point,
    end: Point,
    *,
    spacing_m: float,
    start_offset_m: float = 0.0,
    end_offset_m: float = 0.0,
) -> list[Point]:
    if spacing_m <= 0:
        return []
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= start_offset_m + end_offset_m + 1e-6:
        return []
    ux, uy = dx / length, dy / length
    usable = length - start_offset_m - end_offset_m
    count = int(math.floor(usable / spacing_m)) + 1
    points: list[Point] = []
    for i in range(count):
        dist = start_offset_m + i * spacing_m
        if dist > length - end_offset_m + 1e-6:
            break
        points.append((start[0] + ux * dist, start[1] + uy * dist))
    return points


def suggested_orientation_deg(ring: Ring) -> float:
    """Suggest orientation parallel to the longest edge (degrees from east, CCW)."""
    if len(ring) < 2:
        return 0.0
    closed = close_ring(ring)
    best_len = -1.0
    best_angle = 0.0
    for i in range(len(closed) - 1):
        x1, y1 = closed[i]
        x2, y2 = closed[i + 1]
        length = math.hypot(x2 - x1, y2 - y1)
        if length > best_len:
            best_len = length
            best_angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
    return best_angle
