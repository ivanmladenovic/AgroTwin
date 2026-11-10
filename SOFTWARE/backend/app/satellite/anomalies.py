"""Deterministic first-pass satellite anomaly engine (no disease claims)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.models.enums import SatelliteAnomalyKind


@dataclass(frozen=True)
class ZoneSnapshot:
    zone_key: str
    ndvi: Decimal | None
    ndre: Decimal | None = None
    ndwi: Decimal | None = None


@dataclass(frozen=True)
class AnomalyFinding:
    kind: SatelliteAnomalyKind
    zone_key: str | None
    index_name: str
    severity: float
    message: str
    details: dict


def detect_anomalies(
    *,
    parcel_ndvi_mean: Decimal | None,
    current_zones: Sequence[ZoneSnapshot],
    previous_zones: Sequence[ZoneSnapshot] | None,
    previous_previous_zones: Sequence[ZoneSnapshot] | None = None,
    below_mean_fraction: float = 0.15,
    sudden_decline_fraction: float = 0.20,
) -> list[AnomalyFinding]:
    """Flag potential anomalies only. Never attributes a cause (disease/drought/…)."""
    findings: list[AnomalyFinding] = []
    if parcel_ndvi_mean is None:
        return findings

    prev_by_key = {z.zone_key: z for z in previous_zones or []}
    prev2_by_key = {z.zone_key: z for z in previous_previous_zones or []}

    for zone in current_zones:
        if zone.ndvi is None:
            continue
        # 1) Significantly below parcel mean
        if parcel_ndvi_mean != 0:
            deviation = float((zone.ndvi - parcel_ndvi_mean) / abs(parcel_ndvi_mean))
        else:
            deviation = float(zone.ndvi - parcel_ndvi_mean)
        if deviation <= -below_mean_fraction:
            findings.append(
                AnomalyFinding(
                    kind=SatelliteAnomalyKind.BELOW_PARCEL_MEAN,
                    zone_key=zone.zone_key,
                    index_name="ndvi",
                    severity=abs(deviation),
                    message="Na tom mestu biljke izgledaju slabije (manje zeleno) od ostatka parcele.",
                    details={
                        "zone_ndvi": str(zone.ndvi),
                        "parcel_ndvi_mean": str(parcel_ndvi_mean),
                        "relative_deviation": round(deviation, 4),
                    },
                )
            )

        prev = prev_by_key.get(zone.zone_key)
        if prev and prev.ndvi is not None and prev.ndvi != 0:
            drop = float((zone.ndvi - prev.ndvi) / abs(prev.ndvi))
            if drop <= -sudden_decline_fraction:
                findings.append(
                    AnomalyFinding(
                        kind=SatelliteAnomalyKind.SUDDEN_DECLINE,
                        zone_key=zone.zone_key,
                        index_name="ndvi",
                        severity=abs(drop),
                        message="Na tom mestu biljke su naglo slabije nego na prethodnom snimku.",
                        details={
                            "zone_ndvi": str(zone.ndvi),
                            "previous_ndvi": str(prev.ndvi),
                            "relative_change": round(drop, 4),
                        },
                    )
                )

        # Persistent low: below mean in current + previous (and optionally prev-prev)
        prev2 = prev2_by_key.get(zone.zone_key)
        if (
            deviation <= -below_mean_fraction
            and prev
            and prev.ndvi is not None
            and parcel_ndvi_mean != 0
            and float((prev.ndvi - parcel_ndvi_mean) / abs(parcel_ndvi_mean)) <= -below_mean_fraction
        ):
            consecutive = 2
            if (
                prev2
                and prev2.ndvi is not None
                and float((prev2.ndvi - parcel_ndvi_mean) / abs(parcel_ndvi_mean))
                <= -below_mean_fraction
            ):
                consecutive = 3
            if consecutive >= 2:
                findings.append(
                    AnomalyFinding(
                        kind=SatelliteAnomalyKind.PERSISTENT_LOW,
                        zone_key=zone.zone_key,
                        index_name="ndvi",
                        severity=abs(deviation),
                        message=(
                            "Isto mesto je slabije od ostatka parcele "
                            f"kroz {consecutive} snimka zaredom."
                        ),
                        details={
                            "consecutive_observations": consecutive,
                            "zone_ndvi": str(zone.ndvi),
                            "parcel_ndvi_mean": str(parcel_ndvi_mean),
                        },
                    )
                )

    return findings
