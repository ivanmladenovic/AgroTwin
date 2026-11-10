from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class SatelliteZoneRead(BaseModel):
    zone_key: str
    geometry: dict
    ndvi: Decimal | None = None
    ndre: Decimal | None = None
    ndwi: Decimal | None = None
    ndvi_deviation: Decimal | None = None
    tree_public_ids: list[str] = Field(default_factory=list)


class SatelliteAnomalyRead(BaseModel):
    id: UUID
    zone_key: str | None = None
    tree_public_ids: list[str] = Field(default_factory=list)
    kind: str
    index_name: str
    severity: Decimal
    message: str
    details: dict = Field(default_factory=dict)
    created_at: datetime


class SatelliteObservationSummary(BaseModel):
    id: UUID
    acquisition_date: date
    cloud_cover: Decimal | None = None
    ndvi_mean: Decimal | None = None
    ndre_mean: Decimal | None = None
    ndwi_mean: Decimal | None = None
    anomaly_count: int = 0
    processing_status: str
    provider: str
    satellite: str


class VisualizationLayerRead(BaseModel):
    """Georeferenced index overlay for map ImageOverlay (WGS84 bbox)."""

    index: str
    url: str
    bbox: list[float]  # west, south, east, north
    width: int | None = None
    height: int | None = None
    native_resolution: str | None = None
    display_resolution_m: float | None = None


class SatelliteSampleRead(BaseModel):
    """Point inspect result — never invents pixel values from the display PNG."""

    observation_id: UUID
    index: str
    acquisition_date: date
    longitude: float
    latitude: float
    value: Decimal | None = None
    source: str  # zone_aggregate | unavailable
    zone_key: str | None = None
    message: str


class SatelliteObservationRead(SatelliteObservationSummary):
    parcel_id: UUID
    product_id: str
    acquisition_at: datetime | None = None
    processed_at: datetime | None = None
    ndvi_min: Decimal | None = None
    ndvi_max: Decimal | None = None
    ndvi_stddev: Decimal | None = None
    ndre_min: Decimal | None = None
    ndre_max: Decimal | None = None
    ndwi_min: Decimal | None = None
    ndwi_max: Decimal | None = None
    image_reference: str | None = None
    visualization_refs: dict = Field(default_factory=dict)
    visualization_layers: list[VisualizationLayerRead] = Field(default_factory=list)
    index_formulas: dict = Field(default_factory=dict)
    error_message: str | None = None
    zones: list[SatelliteZoneRead] = Field(default_factory=list)
    anomalies: list[SatelliteAnomalyRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SatelliteChangeRead(BaseModel):
    index_name: str
    latest: Decimal | None = None
    previous: Decimal | None = None
    change_percent: Decimal | None = None


class SatelliteDataCapabilities(BaseModel):
    """Honest flags for what the frontend may render — never imply a raster if none exists."""

    has_boundary: bool = False
    has_centroid: bool = False
    has_aggregate_indices: bool = False
    has_zone_statistics: bool = False
    has_index_raster: bool = False
    has_anomalies: bool = False
    spatial_resolution_note: str | None = None
    sensor: str = "Sentinel-2 L2A"
    display_resolution_m: float = 2.5
    native_resolutions: dict[str, str] = Field(default_factory=dict)
    basemap_note: str | None = (
        "Satelitska podloga (Esri/OSM) nije isti snimak ni datum kao Sentinel-2 opservacija."
    )


class ParcelSatelliteMonitoringRead(BaseModel):
    parcel_id: UUID
    available: bool
    status: str
    message: str | None = None
    provider: str
    index_formulas: dict = Field(default_factory=dict)
    capabilities: SatelliteDataCapabilities = Field(default_factory=SatelliteDataCapabilities)
    latest: SatelliteObservationRead | None = None
    previous: SatelliteObservationRead | None = None
    changes: list[SatelliteChangeRead] = Field(default_factory=list)
    history: list[SatelliteObservationSummary] = Field(default_factory=list)
    anomalies: list[SatelliteAnomalyRead] = Field(default_factory=list)


class SatelliteSyncResultRead(BaseModel):
    parcel_id: UUID
    status: str
    message: str | None = None
    observation_id: UUID | None = None
    skipped_duplicate: bool = False


class SatelliteHistoryPoint(BaseModel):
    observation_id: UUID
    product_id: str
    provider: str
    acquisition_date: date
    processed_at: datetime | None = None
    cloud_cover: Decimal | None = None
    quality: str
    ndvi_mean: Decimal | None = None
    ndre_mean: Decimal | None = None
    ndwi_mean: Decimal | None = None
    ndvi_delta: Decimal | None = None
    ndre_delta: Decimal | None = None
    ndwi_delta: Decimal | None = None
    ndvi_comparison_reliable: bool | None = None
    ndre_comparison_reliable: bool | None = None
    ndwi_comparison_reliable: bool | None = None
    anomaly_count: int = 0
    valid_pixel_counts: dict[str, int] | None = None


class SatelliteAnomalyRecurrence(BaseModel):
    zone_key: str | None = None
    kind: str
    index_name: str
    occurrence_count: int
    acquisition_dates: list[date] = Field(default_factory=list)
    relation: str
    note: str


class SatelliteHistoryRead(BaseModel):
    parcel_id: UUID
    earliest_acquisition_date: date | None = None
    latest_acquisition_date: date | None = None
    date_from: date | None = None
    date_to: date | None = None
    truncated: bool = False
    point_count: int = 0
    points: list[SatelliteHistoryPoint] = Field(default_factory=list)
    repeated_anomalies: list[SatelliteAnomalyRecurrence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
