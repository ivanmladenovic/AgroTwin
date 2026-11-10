"""Filter and KPI helpers for Enterprise watch of existing parcel alerts.

Does not create alerts and does not change producer status.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def assignment_is_readable(
    *,
    assignment_status: str,
    supplier_status: str,
    valid_from: date | None,
    valid_until: date | None,
    on_date: date,
) -> bool:
    if assignment_status != "active" or supplier_status != "active":
        return False
    if valid_from is not None and valid_from > on_date:
        return False
    if valid_until is not None and valid_until < on_date:
        return False
    return True


def intelligence_href(parcel_id: str, alert_id: str) -> str:
    """Existing producer Intelligence route. Query only scrolls to the alert."""
    return f"/orchard/{parcel_id}/intelligence?alert={alert_id}"


def alert_scene_date(evidence: dict | None, created_on: date | None) -> date | None:
    raw = (evidence or {}).get("observation_date")
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            return None
    return created_on


def affected_indices(evidence: dict | None) -> list[str]:
    raw = (evidence or {}).get("affected_indices") or []
    found: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        key = item.strip().lower()
        if key and key not in found:
            found.append(key)
    return found


def filter_alert_rows(
    rows: list[dict[str, Any]],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    farm_id: str | None = None,
    parcel_id: str | None = None,
    index: str | None = None,
    severity: str | None = None,
    alert_status: str | None = None,
    review_status: str | None = None,
) -> list[dict[str, Any]]:
    """One row per alert id. Index filter does not split a multi-index alert."""
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    index_key = index.strip().lower() if index else None
    for row in rows:
        alert_id = str(row["alert_id"])
        if alert_id in seen:
            continue
        seen.add(alert_id)
        if farm_id and str(row.get("farm_id")) != farm_id:
            continue
        if parcel_id and str(row.get("parcel_id")) != parcel_id:
            continue
        if severity and str(row.get("severity")) != severity:
            continue
        if alert_status and str(row.get("status")) != alert_status:
            continue
        reviewed = bool(row.get("reviewed"))
        if review_status == "reviewed" and not reviewed:
            continue
        if review_status == "unreviewed" and reviewed:
            continue
        if index_key and index_key not in (row.get("affected_indices") or []):
            continue
        scene = row.get("scene_date")
        if date_from and (scene is None or scene < date_from):
            continue
        if date_to and (scene is None or scene > date_to):
            continue
        kept.append(row)
    return kept


def alert_kpis(rows: list[dict[str, Any]], *, satellite_anomaly_count: int) -> dict[str, int]:
    open_statuses = {"open", "acknowledged"}
    return {
        "open_alerts": sum(1 for row in rows if row.get("status") in open_statuses),
        "alert_count": len(rows),
        "satellite_anomaly_count": satellite_anomaly_count,
    }
