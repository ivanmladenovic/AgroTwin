"""Classify assigned parcels by existing satellite and completeness rules.

Does not sync satellite data and does not change the four-field completeness score.
A missing scene is not an orchard problem. Short history is not a vegetation anomaly.
"""

from __future__ import annotations

QUALITY_CLOUD_PERCENT = 30.0
REQUIRED_COMPLETENESS = ("area_hectares", "variety", "planting_year", "trees")

SATELLITE_NOTES = [
    "Snimak sa oblačnošću ispod 30% je postojeći prag kvalitetne opservacije.",
    "Dve takve opservacije u sezoni su minimum za poređenje. Manje od toga nije anomalija vegetacije.",
    "Parcela bez snimka nije dokaz lošeg stanja zasada.",
    "Nepotpuni podaci su površina, sorta, godina sadnje i bar jedno stablo. Granica parcele nije u tom broju.",
]


def satellite_buckets(observations: list[tuple[str, float | None]]) -> set[str]:
    """observations are (processing_status, cloud_cover) already limited to the season."""
    if not observations:
        return {"no_scene", "insufficient_history"}
    usable = 0
    for status, cloud in observations:
        if status == "completed" and cloud is not None and cloud < QUALITY_CLOUD_PERCENT:
            usable += 1
    buckets: set[str] = set()
    if usable >= 1:
        buckets.add("usable_scene")
    else:
        buckets.add("cloudy_only")
    if usable < 2:
        buckets.add("insufficient_history")
    return buckets


def business_buckets(*, open_alert: bool, missing_fields: list[str]) -> set[str]:
    buckets: set[str] = set()
    if open_alert:
        buckets.add("open_alert")
    if any(field in missing_fields for field in REQUIRED_COMPLETENESS):
        buckets.add("incomplete")
    return buckets
