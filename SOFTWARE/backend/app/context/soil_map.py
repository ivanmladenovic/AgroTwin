"""Map cached SoilGrids snapshots into context without calling the provider."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.soil import SoilProfileSnapshot
from app.soil.properties import (
    PROPERTY_SPECS,
    PROVIDER_NAME,
    SOURCE_LABEL,
    SOURCE_TYPE,
    depth_label,
    stored_depth_value,
)


def snapshot_is_stale(snapshot: SoilProfileSnapshot, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    expires = snapshot.expires_at
    if expires is None:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current >= expires.astimezone(timezone.utc)


def surface_properties(values: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    stored = values if isinstance(values, dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for spec in PROPERTY_SPECS:
        raw = stored.get(spec.key)
        if not isinstance(raw, dict):
            result[spec.key] = {
                "key": spec.key,
                "label": spec.label,
                "unit": spec.display_unit,
                "value": None,
                "depth": None,
                "depth_label": None,
                "available": False,
            }
            continue
        surface = None
        for depth_key, payload in raw.items():
            parsed = stored_depth_value(payload)
            if parsed is None:
                continue
            surface = {
                "key": spec.key,
                "label": spec.label,
                "unit": parsed.unit or spec.display_unit,
                "value": parsed.value,
                "depth": depth_key,
                "depth_label": depth_label(depth_key),
                "available": True,
            }
            break
        result[spec.key] = surface or {
            "key": spec.key,
            "label": spec.label,
            "unit": spec.display_unit,
            "value": None,
            "depth": None,
            "depth_label": None,
            "available": False,
        }
    return result


def source_meta() -> dict[str, str]:
    return {
        "source": PROVIDER_NAME,
        "source_type": SOURCE_TYPE,
        "source_label": SOURCE_LABEL,
    }
