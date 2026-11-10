"""Provider-agnostic satellite interface.

Concrete providers (Copernicus CDSE, future commercial APIs) implement this
protocol. Application services must depend on SatelliteProvider, never on a
specific vendor SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, Sequence

from app.satellite.indices import IndexName


@dataclass(frozen=True)
class SatelliteImageCandidate:
    image_id: str
    product_id: str
    acquisition_date: date
    acquisition_at: datetime | None
    cloud_cover: float | None
    satellite: str
    collection: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexStatistics:
    mean: float | None
    min: float | None
    max: float | None
    stddev: float | None = None
    valid_pixel_count: int = 0


@dataclass(frozen=True)
class ZoneIndexResult:
    zone_key: str
    geometry: dict[str, Any]
    ndvi: IndexStatistics | None = None
    ndre: IndexStatistics | None = None
    ndwi: IndexStatistics | None = None


@dataclass(frozen=True)
class IndexCalculationResult:
    image_id: str
    product_id: str
    acquisition_date: date
    acquisition_at: datetime | None
    cloud_cover: float | None
    satellite: str
    ndvi: IndexStatistics
    ndre: IndexStatistics
    ndwi: IndexStatistics
    zones: tuple[ZoneIndexResult, ...] = ()
    image_reference: str | None = None
    visualization_refs: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisualizationAsset:
    index: IndexName
    content_type: str
    content: bytes
    width: int | None = None
    height: int | None = None
    # Geographic bounds of the PNG in WGS84: west, south, east, north.
    bbox: tuple[float, float, float, float] | None = None


class SatelliteProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, code: str = "provider_error") -> None:
        self.message = message
        self.retryable = retryable
        self.code = code
        super().__init__(message)


class SatelliteProvider(Protocol):
    """Swap-friendly satellite data provider."""

    name: str

    def search_available_images(
        self,
        parcel_geometry: dict[str, Any],
        start_date: date,
        end_date: date,
        max_cloud_cover: float,
    ) -> list[SatelliteImageCandidate]: ...

    def get_image_metadata(self, image_id: str) -> SatelliteImageCandidate: ...

    def calculate_indices(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        indices: Sequence[IndexName],
        *,
        zone_geometries: Sequence[tuple[str, dict[str, Any]]] | None = None,
    ) -> IndexCalculationResult: ...

    def get_visualization(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        index: IndexName,
    ) -> VisualizationAsset: ...

    def get_statistics(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        index: IndexName,
    ) -> IndexStatistics: ...
