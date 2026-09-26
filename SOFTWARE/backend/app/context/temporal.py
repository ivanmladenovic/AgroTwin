"""Temporal relation labels. Metadata only — no causality."""

from __future__ import annotations

from datetime import date

from app.context.types import TemporalRelation


def temporal_relation(
    record_date: date | None,
    event_date: date,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> TemporalRelation:
    if period_start is not None and period_end is not None:
        if period_start <= event_date <= period_end:
            if record_date is None or period_start <= record_date <= period_end:
                return TemporalRelation.DURING_PERIOD
    if record_date is None:
        return TemporalRelation.HISTORICAL
    if record_date < event_date:
        return TemporalRelation.BEFORE_EVENT
    if record_date > event_date:
        return TemporalRelation.AFTER_EVENT
    return TemporalRelation.CURRENT
