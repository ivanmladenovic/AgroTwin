"""Decide whether AI should run — cost control before any model call."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence


@dataclass(frozen=True)
class ChangeSignal:
    code: str
    description: str
    severity_hint: str = "INFO"


@dataclass(frozen=True)
class ChangeDetectionResult:
    should_call_ai: bool
    reason: str
    signals: tuple[ChangeSignal, ...] = ()
    fingerprint: str = ""


def detect_meaningful_changes(
    *,
    force: bool,
    trigger_kinds: Sequence[str],
    latest_satellite: dict[str, Any] | None,
    previous_satellite: dict[str, Any] | None,
    anomaly_count: int,
    recent_activity_slugs: Sequence[str],
    yield_deviation_percent: Decimal | None,
    open_alert_count: int,
    last_analysis_at: datetime | None,
    min_interval_hours: float,
    ndvi_change_threshold: float = 0.08,
) -> ChangeDetectionResult:
    """Return whether the AI model should be invoked."""
    now = datetime.now(timezone.utc)
    signals: list[ChangeSignal] = []

    if force or "manual_request" in trigger_kinds:
        return ChangeDetectionResult(
            should_call_ai=True,
            reason="manual_or_forced",
            signals=(ChangeSignal("manual", "Manual analysis requested"),),
            fingerprint=_fingerprint(["manual", *trigger_kinds]),
        )

    if last_analysis_at is not None:
        age_hours = (now - last_analysis_at).total_seconds() / 3600.0
        if age_hours < min_interval_hours and "scheduled" in trigger_kinds and len(trigger_kinds) == 1:
            return ChangeDetectionResult(
                should_call_ai=False,
                reason="min_interval_not_elapsed",
                fingerprint="interval",
            )

    if anomaly_count > 0 or "satellite_anomaly" in trigger_kinds:
        signals.append(
            ChangeSignal(
                "satellite_anomaly",
                f"Satellite anomaly count={anomaly_count}",
                "WARNING",
            )
        )

    if latest_satellite and previous_satellite:
        for key, label in (("ndvi_mean", "NDVI"), ("ndre_mean", "NDRE"), ("ndwi_mean", "NDWI")):
            cur = _as_float(latest_satellite.get(key))
            prev = _as_float(previous_satellite.get(key))
            if cur is None or prev is None:
                continue
            delta = cur - prev
            if abs(delta) >= ndvi_change_threshold:
                signals.append(
                    ChangeSignal(
                        f"{key}_change",
                        f"{label} changed by {delta:+.3f}",
                        "WARNING" if abs(delta) >= ndvi_change_threshold * 1.5 else "INFO",
                    )
                )

    if "satellite_observation" in trigger_kinds and not previous_satellite:
        signals.append(ChangeSignal("first_satellite", "First satellite observation available"))

    for slug in recent_activity_slugs:
        signals.append(ChangeSignal(f"activity_{slug}", f"Recent activity: {slug}", "INFO"))

    if yield_deviation_percent is not None and abs(float(yield_deviation_percent)) >= 20:
        signals.append(
            ChangeSignal(
                "yield_deviation",
                f"Actual vs expected yield deviation {yield_deviation_percent}%",
                "WARNING",
            )
        )

    if "weather_event" in trigger_kinds:
        signals.append(ChangeSignal("weather_event", "Relevant weather event flagged", "WARNING"))

    if "harvest_recorded" in trigger_kinds:
        signals.append(ChangeSignal("harvest", "New harvest recorded", "INFO"))

    if not signals:
        # Periodic check with open alerts still worth a light look only if interval elapsed.
        if open_alert_count > 0 and (
            last_analysis_at is None
            or (now - last_analysis_at).total_seconds() / 3600.0 >= min_interval_hours
        ):
            signals.append(
                ChangeSignal("open_alerts_review", f"{open_alert_count} unresolved alert(s)", "INFO")
            )
        else:
            return ChangeDetectionResult(
                should_call_ai=False,
                reason="no_meaningful_change",
                fingerprint="none",
            )

    return ChangeDetectionResult(
        should_call_ai=True,
        reason="meaningful_change",
        signals=tuple(signals),
        fingerprint=_fingerprint([s.code for s in signals]),
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fingerprint(parts: Sequence[str]) -> str:
    return "|".join(sorted({part for part in parts if part}))
