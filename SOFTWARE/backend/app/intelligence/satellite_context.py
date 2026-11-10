"""Compact satellite + zone anomaly payloads for AgroTwin Intelligence AI context."""

from __future__ import annotations

from typing import Any

# Cap anomalies sent to the model (prioritize by severity).
MAX_ANOMALIES = 12


def sat_observation_summary(observation) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "acquisition_date": observation.acquisition_date.isoformat()
        if observation.acquisition_date
        else None,
        "cloud_cover": _str_or_none(observation.cloud_cover),
        "ndvi_mean": _str_or_none(observation.ndvi_mean),
        "ndvi_min": _str_or_none(getattr(observation, "ndvi_min", None)),
        "ndvi_max": _str_or_none(getattr(observation, "ndvi_max", None)),
        "ndre_mean": _str_or_none(observation.ndre_mean),
        "ndwi_mean": _str_or_none(observation.ndwi_mean),
        "anomaly_count": int(observation.anomaly_count or 0),
        "processing_status": getattr(observation.processing_status, "value", None)
        or str(getattr(observation, "processing_status", "") or "")
        or None,
        "data_quality_notes": _observation_quality_notes(observation),
    }


def serialize_zone_anomalies(
    observation,
    *,
    trees: list[Any] | None = None,
    parcel_boundary: dict[str, Any] | None = None,
    limit: int = MAX_ANOMALIES,
) -> list[dict[str, Any]]:
    """Structured zone-level anomalies already persisted by the satellite service.

    Does not recalculate indices. Missing history fields are explicit nulls.
    When trees with coordinates are provided, attaches tree_public_ids per zone.
    """
    if observation is None:
        return []
    anomalies = list(getattr(observation, "anomalies", None) or [])
    if not anomalies:
        return []

    from app.satellite.zone_trees import format_tree_ids_label, trees_in_zone_geometry

    zone_by_key = {
        z.zone_key: z
        for z in (getattr(observation, "zones", None) or [])
        if getattr(z, "zone_key", None)
    }
    tree_list = list(trees or [])

    ranked = sorted(
        anomalies,
        key=lambda item: float(item.severity or 0),
        reverse=True,
    )[:limit]

    out: list[dict[str, Any]] = []
    for item in ranked:
        details = item.details if isinstance(item.details, dict) else {}
        zone = zone_by_key.get(item.zone_key) if item.zone_key else None
        index_name = (item.index_name or "ndvi").lower()
        zone_value = _zone_index_value(zone, index_name)
        geometry = getattr(zone, "geometry", None) if zone is not None else None
        tree_ids = trees_in_zone_geometry(
            geometry if isinstance(geometry, dict) else None,
            tree_list,
            parcel_boundary=parcel_boundary,
        )
        location_hint = format_tree_ids_label(tree_ids) or _zone_location_hint(item.zone_key)
        out.append(
            {
                "zone_key": item.zone_key,
                "tree_public_ids": tree_ids,
                "zone_location_hint": location_hint,
                "kind": item.kind.value if hasattr(item.kind, "value") else str(item.kind),
                "index_name": index_name,
                "severity": _str_or_none(item.severity),
                "message": item.message,
                "zone_value": zone_value,
                "parcel_reference_value": details.get("parcel_ndvi_mean")
                if index_name == "ndvi"
                else None,
                "previous_value": details.get("previous_ndvi"),
                "relative_deviation": details.get("relative_deviation"),
                "relative_change": details.get("relative_change"),
                "consecutive_observations": details.get("consecutive_observations"),
                "details": {
                    key: details.get(key)
                    for key in (
                        "zone_ndvi",
                        "parcel_ndvi_mean",
                        "previous_ndvi",
                        "relative_deviation",
                        "relative_change",
                        "consecutive_observations",
                    )
                    if key in details
                },
                "comparison_available": _comparison_available(item, details),
            }
        )
    return out


def _comparison_available(item, details: dict) -> str:
    kind = item.kind.value if hasattr(item.kind, "value") else str(item.kind)
    if kind == "sudden_decline":
        if details.get("previous_ndvi") is None:
            return "insufficient_history"
        return "vs_previous_observation"
    if kind == "persistent_low":
        consecutive = details.get("consecutive_observations")
        if consecutive is None:
            return "insufficient_history"
        return f"persistent_{consecutive}_observations"
    if kind == "below_parcel_mean":
        if details.get("parcel_ndvi_mean") is None:
            return "insufficient_parcel_reference"
        return "vs_parcel_mean"
    return "unknown"


def _zone_index_value(zone, index_name: str) -> str | None:
    if zone is None:
        return None
    if index_name == "ndre":
        return _str_or_none(zone.ndre)
    if index_name == "ndwi":
        return _str_or_none(zone.ndwi)
    return _str_or_none(zone.ndvi)


def _zone_location_hint(zone_key: str | None) -> str | None:
    """Human-oriented grid hint without claiming a tree ID."""
    if not zone_key:
        return None
    import re

    match = re.match(r"^r(\d+)c(\d+)$", zone_key.strip(), re.I)
    if not match:
        return zone_key
    row = int(match.group(1)) + 1
    col = int(match.group(2)) + 1
    return f"grid_cell_row_{row}_col_{col}"


def _observation_quality_notes(observation) -> list[str]:
    notes: list[str] = []
    cloud = observation.cloud_cover
    if cloud is not None:
        try:
            cloud_f = float(cloud)
            notes.append(f"cloud_cover_percent={cloud_f:.1f}")
            if cloud_f >= 30:
                notes.append("elevated_cloud_cover_may_affect_index_reliability")
        except (TypeError, ValueError):
            notes.append(f"cloud_cover={cloud}")
    status = getattr(observation, "processing_status", None)
    status_val = getattr(status, "value", None) or str(status or "")
    if status_val and status_val not in {"completed", "COMPLETED"}:
        notes.append(f"processing_status={status_val}")
    return notes


def _str_or_none(value) -> str | None:
    if value is None:
        return None
    return str(value)
