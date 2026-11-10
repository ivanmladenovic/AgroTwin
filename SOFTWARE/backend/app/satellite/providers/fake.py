"""Deterministic fake provider for unit tests and local demos without CDSE credentials."""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from app.satellite.indices import IndexName, ndre, ndvi, ndwi_gao
from app.satellite.providers.base import (
    IndexCalculationResult,
    IndexStatistics,
    SatelliteImageCandidate,
    SatelliteProviderError,
    VisualizationAsset,
    ZoneIndexResult,
)
from app.satellite.zones import build_zone_grid, parcel_bbox


class FakeSatelliteProvider:
    name = "fake"

    def __init__(self, *, seed: str = "agrotwin") -> None:
        self.seed = seed

    def search_available_images(
        self,
        parcel_geometry: dict[str, Any],
        start_date: date,
        end_date: date,
        max_cloud_cover: float,
    ) -> list[SatelliteImageCandidate]:
        if start_date > end_date:
            return []
        # One scene every 5 days with cloud cover cycling 5 → 35.
        results: list[SatelliteImageCandidate] = []
        cursor = start_date
        day = 0
        while cursor <= end_date:
            cloud = float((day * 7) % 36)
            if cloud <= max_cloud_cover:
                image_id = f"FAKE-S2-{cursor.isoformat()}"
                results.append(
                    SatelliteImageCandidate(
                        image_id=image_id,
                        product_id=image_id,
                        acquisition_date=cursor,
                        acquisition_at=datetime(
                            cursor.year, cursor.month, cursor.day, 10, 0, tzinfo=timezone.utc
                        ),
                        cloud_cover=cloud,
                        satellite="Sentinel-2",
                        collection="sentinel-2-l2a",
                        metadata={"fake": True},
                    )
                )
            cursor += timedelta(days=5)
            day += 1
        results.sort(key=lambda item: item.acquisition_date, reverse=True)
        return results

    def get_image_metadata(self, image_id: str) -> SatelliteImageCandidate:
        if not image_id.startswith("FAKE-S2-"):
            raise SatelliteProviderError(f"Unknown fake image {image_id}", retryable=False)
        raw = image_id.removeprefix("FAKE-S2-")
        acquisition_date = date.fromisoformat(raw)
        return SatelliteImageCandidate(
            image_id=image_id,
            product_id=image_id,
            acquisition_date=acquisition_date,
            acquisition_at=datetime(
                acquisition_date.year,
                acquisition_date.month,
                acquisition_date.day,
                10,
                0,
                tzinfo=timezone.utc,
            ),
            cloud_cover=10.0,
            satellite="Sentinel-2",
            collection="sentinel-2-l2a",
            metadata={"fake": True},
        )

    def calculate_indices(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        indices: Sequence[IndexName],
        *,
        zone_geometries: Sequence[tuple[str, dict[str, Any]]] | None = None,
    ) -> IndexCalculationResult:
        meta = self.get_image_metadata(image_id)
        zones_src = list(zone_geometries) if zone_geometries else build_zone_grid(parcel_geometry)
        zone_results: list[ZoneIndexResult] = []
        ndvi_vals: list[float] = []
        ndre_vals: list[float] = []
        ndwi_vals: list[float] = []
        for zone_key, geom in zones_src:
            values = self._zone_band_values(image_id, zone_key, geom)
            z_ndvi = ndvi(values["b08"], values["b04"])
            z_ndre = ndre(values["b8a"], values["b05"])
            z_ndwi = ndwi_gao(values["b08"], values["b11"])
            if z_ndvi is not None:
                ndvi_vals.append(z_ndvi)
            if z_ndre is not None:
                ndre_vals.append(z_ndre)
            if z_ndwi is not None:
                ndwi_vals.append(z_ndwi)
            zone_results.append(
                ZoneIndexResult(
                    zone_key=zone_key,
                    geometry=geom,
                    ndvi=_stats_from_values([z_ndvi] if z_ndvi is not None else []),
                    ndre=_stats_from_values([z_ndre] if z_ndre is not None else []),
                    ndwi=_stats_from_values([z_ndwi] if z_ndwi is not None else []),
                )
            )
        return IndexCalculationResult(
            image_id=meta.image_id,
            product_id=meta.product_id,
            acquisition_date=meta.acquisition_date,
            acquisition_at=meta.acquisition_at,
            cloud_cover=meta.cloud_cover,
            satellite=meta.satellite,
            ndvi=_stats_from_values(ndvi_vals),
            ndre=_stats_from_values(ndre_vals),
            ndwi=_stats_from_values(ndwi_vals),
            zones=tuple(zone_results),
            image_reference=meta.product_id,
            metadata={"provider": self.name, "formulas": "see INDEX_FORMULAS"},
        )

    def get_visualization(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        index: IndexName,
    ) -> VisualizationAsset:
        # Minimal 1×1 PNG — tests assert storage/serving, not visual quality.
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
            b"\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        west, south, east, north = parcel_bbox(parcel_geometry)
        return VisualizationAsset(
            index=index,
            content_type="image/png",
            content=png,
            width=1,
            height=1,
            bbox=(west, south, east, north),
        )

    def get_statistics(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        index: IndexName,
    ) -> IndexStatistics:
        result = self.calculate_indices(parcel_geometry, image_id, [index])
        if index == IndexName.NDVI:
            return result.ndvi
        if index == IndexName.NDRE:
            return result.ndre
        return result.ndwi

    def _zone_band_values(self, image_id: str, zone_key: str, geometry: dict[str, Any]) -> dict[str, float]:
        digest = hashlib.sha256(f"{self.seed}:{image_id}:{zone_key}".encode()).hexdigest()
        base = int(digest[:8], 16) / 0xFFFFFFFF
        min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
        spatial = ((min_lon + max_lon) / 2 + (min_lat + max_lat) / 2) % 1.0
        green = 0.25 + 0.45 * base + 0.15 * math.sin(spatial * 6.28)
        # Inject a persistent weak zone for anomaly tests.
        if zone_key.endswith("c0") and zone_key.startswith("r0"):
            green *= 0.55
        red = max(0.05, green * 0.35)
        red_edge = max(0.05, green * 0.55)
        swir = max(0.05, green * 0.4)
        nir = max(0.1, green)
        nir_narrow = max(0.1, green * 1.05)
        return {"b04": red, "b05": red_edge, "b08": nir, "b8a": nir_narrow, "b11": swir}


def _stats_from_values(values: list[float]) -> IndexStatistics:
    if not values:
        return IndexStatistics(mean=None, min=None, max=None, stddev=None, valid_pixel_count=0)
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return IndexStatistics(
        mean=mean,
        min=min(values),
        max=max(values),
        stddev=math.sqrt(variance),
        valid_pixel_count=len(values),
    )
