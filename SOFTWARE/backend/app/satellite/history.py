"""Time series and repeated-zone view over stored satellite observations.

Reads aggregates already persisted by SatelliteService. Does not call a
provider, does not invent dates between scenes, and does not turn null
index means into zero.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

# Same cloud note already used when describing observation quality to Intelligence.
# This is not an anomaly threshold and does not change NDVI/NDRE/NDWI detection.
ELEVATED_CLOUD_PERCENT = 30.0
MAX_HISTORY_POINTS = 120


def build_satellite_history(
    observations: list[Any],
    *,
    parcel_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = MAX_HISTORY_POINTS,
) -> dict[str, Any]:
    """Build a parcel-scoped series and repeated anomaly groups."""
    owned = [item for item in observations if getattr(item, "parcel_id", None) == parcel_id]
    deduped = _dedupe_by_product(owned)
    dated = [item for item in deduped if getattr(item, "acquisition_date", None) is not None]
    dated.sort(key=lambda item: (item.acquisition_date, _processed_sort(item), str(item.id)))

    notes: list[str] = []
    earliest = dated[0].acquisition_date if dated else None
    latest = dated[-1].acquisition_date if dated else None
    if earliest is None:
        notes.append("Nema sačuvanih satelitskih opservacija za ovu parcelu.")
    else:
        notes.append(
            f"Sačuvani snimci počinju od {earliest.isoformat()}. "
            "Datumi između snimaka nisu mereni."
        )
    notes.append(
        "Udeo validnih piksela postoji samo na opservacijama obrađenim posle uvođenja tog zapisa. "
        "Stariji snimci nemaju to polje."
    )

    window = [
        item
        for item in dated
        if (date_from is None or item.acquisition_date >= date_from)
        and (date_to is None or item.acquisition_date <= date_to)
    ]
    truncated = len(window) > limit
    if truncated:
        window = window[-limit:]
        notes.append(f"Prikazano je poslednjih {limit} snimaka u izabranom periodu.")

    points = _points(window)
    repeated = _repeated_anomalies(window)
    if len(window) < 2:
        notes.append("Nema dovoljno snimaka za poređenje ponovljenih zona.")
    elif not repeated:
        notes.append("U izabranom periodu nema zone koja se ponavlja na više snimaka.")

    return {
        "parcel_id": parcel_id,
        "earliest_acquisition_date": earliest,
        "latest_acquisition_date": latest,
        "date_from": date_from,
        "date_to": date_to,
        "truncated": truncated,
        "point_count": len(points),
        "points": points,
        "repeated_anomalies": repeated,
        "notes": notes,
    }


def _dedupe_by_product(observations: list[Any]) -> list[Any]:
    """One row per provider+product. Keep the later processing, never average."""
    chosen: dict[tuple[str, str], Any] = {}
    for item in observations:
        key = (str(getattr(item, "provider", "") or ""), str(getattr(item, "product_id", "") or ""))
        if not key[1]:
            key = (key[0], str(getattr(item, "id", "")))
        current = chosen.get(key)
        if current is None or _processed_sort(item) >= _processed_sort(current):
            chosen[key] = item
    return list(chosen.values())


def _processed_sort(item: Any) -> datetime:
    processed = getattr(item, "processed_at", None)
    if isinstance(processed, datetime):
        return processed
    created = getattr(item, "created_at", None)
    if isinstance(created, datetime):
        return created
    return datetime.min


def _points(observations: list[Any]) -> list[dict[str, Any]]:
    previous_value: dict[str, Decimal | None] = {"ndvi": None, "ndre": None, "ndwi": None}
    previous_quality: dict[str, str | None] = {"ndvi": None, "ndre": None, "ndwi": None}
    points: list[dict[str, Any]] = []
    for item in observations:
        quality = _quality(getattr(item, "cloud_cover", None))
        means = {
            "ndvi": _decimal_or_none(getattr(item, "ndvi_mean", None)),
            "ndre": _decimal_or_none(getattr(item, "ndre_mean", None)),
            "ndwi": _decimal_or_none(getattr(item, "ndwi_mean", None)),
        }
        deltas: dict[str, Decimal | None] = {}
        reliable: dict[str, bool | None] = {}
        for index, value in means.items():
            prev = previous_value[index]
            if value is None or prev is None:
                deltas[index] = None
                reliable[index] = None
            else:
                deltas[index] = (value - prev).quantize(Decimal("0.0001"))
                reliable[index] = quality == "ok" and previous_quality[index] == "ok"
            if value is not None:
                previous_value[index] = value
                previous_quality[index] = quality
        points.append(
            {
                "observation_id": item.id,
                "product_id": str(getattr(item, "product_id", "") or ""),
                "provider": str(getattr(item, "provider", "") or ""),
                "acquisition_date": item.acquisition_date,
                "processed_at": getattr(item, "processed_at", None),
                "cloud_cover": _decimal_or_none(getattr(item, "cloud_cover", None)),
                "quality": quality,
                "ndvi_mean": means["ndvi"],
                "ndre_mean": means["ndre"],
                "ndwi_mean": means["ndwi"],
                "ndvi_delta": deltas["ndvi"],
                "ndre_delta": deltas["ndre"],
                "ndwi_delta": deltas["ndwi"],
                "ndvi_comparison_reliable": reliable["ndvi"],
                "ndre_comparison_reliable": reliable["ndre"],
                "ndwi_comparison_reliable": reliable["ndwi"],
                "anomaly_count": int(getattr(item, "anomaly_count", 0) or 0),
                "valid_pixel_counts": _valid_pixels(item),
            }
        )
    return points


def _quality(cloud_cover: Any) -> str:
    cloud = _decimal_or_none(cloud_cover)
    if cloud is None:
        return "unknown"
    if float(cloud) >= ELEVATED_CLOUD_PERCENT:
        return "elevated_cloud"
    return "ok"


def _valid_pixels(item: Any) -> dict[str, int] | None:
    meta = getattr(item, "source_metadata", None)
    if not isinstance(meta, dict):
        return None
    raw = meta.get("valid_pixel_counts")
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key in ("ndvi", "ndre", "ndwi"):
        value = raw.get(key)
        if isinstance(value, bool) or value is None:
            continue
        try:
            out[key] = int(value)
        except (TypeError, ValueError):
            continue
    return out or None


def _repeated_anomalies(observations: list[Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in observations:
        zones = {
            zone.zone_key: zone
            for zone in (getattr(item, "zones", None) or [])
            if getattr(zone, "zone_key", None)
        }
        for anomaly in getattr(item, "anomalies", None) or []:
            zone_key = getattr(anomaly, "zone_key", None) or ""
            kind = _enum_value(getattr(anomaly, "kind", None))
            index_name = str(getattr(anomaly, "index_name", None) or "ndvi").lower()
            key = (zone_key, kind, index_name)
            bucket = groups.setdefault(
                key,
                {
                    "zone_key": zone_key or None,
                    "kind": kind,
                    "index_name": index_name,
                    "dates": [],
                    "bboxes": [],
                },
            )
            if item.acquisition_date not in bucket["dates"]:
                bucket["dates"].append(item.acquisition_date)
            zone = zones.get(zone_key) if zone_key else None
            bbox = _geometry_bbox(getattr(zone, "geometry", None) if zone is not None else None)
            bucket["bboxes"].append(bbox)

    repeated: list[dict[str, Any]] = []
    for bucket in groups.values():
        if len(bucket["dates"]) < 2:
            continue
        relation, note = _relation(bucket["bboxes"])
        repeated.append(
            {
                "zone_key": bucket["zone_key"],
                "kind": bucket["kind"],
                "index_name": bucket["index_name"],
                "occurrence_count": len(bucket["dates"]),
                "acquisition_dates": bucket["dates"],
                "relation": relation,
                "note": note,
            }
        )
    repeated.sort(key=lambda row: (-row["occurrence_count"], row["zone_key"] or "", row["kind"]))
    return repeated


def _relation(bboxes: list[tuple[float, float, float, float] | None]) -> tuple[str, str]:
    present = [bbox for bbox in bboxes if bbox is not None]
    if len(present) < 2:
        return (
            "potentially_related",
            "Isti ključ zone se ponavlja, ali geometrija ćelije nije sačuvana na svim snimcima. "
            "Nije potvrđeno da je to ista lokacija.",
        )
    first = present[0]
    if all(_iou(first, other) >= 0.5 for other in present[1:]):
        return (
            "same_grid_cell",
            "Ista ćelija mreže (preklapanje granica zone) na više snimaka.",
        )
    return (
        "potentially_related",
        "Ključ zone se poklapa, ali geometrija ćelije nije ista. "
        "Moguće je da se mreža pomerila posle izmene granice parcele.",
    )


def _geometry_bbox(geometry: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(geometry, dict):
        return None
    coords: list[tuple[float, float]] = []

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)) and len(node) >= 2 and isinstance(node[0], (int, float)):
            coords.append((float(node[0]), float(node[1])))
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(geometry.get("coordinates"))
    if len(coords) < 3:
        return None
    lons = [lon for lon, _ in coords]
    lats = [lat for _, lat in coords]
    return min(lons), min(lats), max(lons), max(lats)


def _iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    ix0 = max(left[0], right[0])
    iy0 = max(left[1], right[1])
    ix1 = min(left[2], right[2])
    iy1 = min(left[3], right[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    area_l = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_r = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = area_l + area_r - inter
    if union <= 0:
        return 0.0
    return inter / union


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return Decimal(str(value))


def _enum_value(value: Any) -> str:
    if value is None:
        return "unknown"
    return value.value if hasattr(value, "value") else str(value)
