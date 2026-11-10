"""Select the best Sentinel-2 scene for a parcel with progressive cloud thresholds."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from app.satellite.providers.base import SatelliteImageCandidate, SatelliteProvider, SatelliteProviderError


DEFAULT_CLOUD_THRESHOLDS: tuple[float, ...] = (20.0, 30.0, 40.0)


def select_best_image(
    provider: SatelliteProvider,
    parcel_geometry: dict,
    start_date: date,
    end_date: date,
    *,
    cloud_thresholds: Sequence[float] = DEFAULT_CLOUD_THRESHOLDS,
    absolute_max_cloud: float = 40.0,
) -> tuple[SatelliteImageCandidate | None, float | None]:
    """Prefer the newest valid image under the lowest workable cloud threshold.

    Returns (candidate, threshold_used). Never returns a candidate whose
    reported cloud cover exceeds ``absolute_max_cloud``.
    """
    last_error: Exception | None = None
    for threshold in cloud_thresholds:
        if threshold > absolute_max_cloud:
            continue
        try:
            candidates = provider.search_available_images(
                parcel_geometry,
                start_date,
                end_date,
                max_cloud_cover=threshold,
            )
        except SatelliteProviderError as exc:
            last_error = exc
            if not exc.retryable:
                raise
            continue
        valid = [
            item
            for item in candidates
            if item.cloud_cover is None or item.cloud_cover <= absolute_max_cloud
        ]
        if not valid:
            continue
        # Newest first; then lowest cloud cover as tie-breaker.
        valid.sort(
            key=lambda item: (
                item.acquisition_date,
                -(item.cloud_cover if item.cloud_cover is not None else 100.0),
            ),
            reverse=True,
        )
        return valid[0], float(threshold)
    if last_error is not None:
        raise last_error
    return None, None
