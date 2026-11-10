"""Resolve the configured satellite provider implementation."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.satellite.providers.base import SatelliteProvider
from app.satellite.providers.copernicus import CopernicusDataSpaceProvider
from app.satellite.providers.fake import FakeSatelliteProvider


@lru_cache
def get_satellite_provider() -> SatelliteProvider:
    settings = get_settings()
    name = (settings.satellite_provider or "copernicus").strip().lower()
    if name in {"fake", "demo", "test"}:
        return FakeSatelliteProvider()
    if name in {"copernicus", "copernicus_cdse", "cdse"}:
        return CopernicusDataSpaceProvider()
    raise ValueError(f"Unsupported SATELLITE_PROVIDER={settings.satellite_provider!r}")


def reload_satellite_provider() -> SatelliteProvider:
    get_satellite_provider.cache_clear()
    return get_satellite_provider()
