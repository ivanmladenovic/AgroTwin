"""Copernicus Data Space Ecosystem provider (STAC discovery + Sentinel Hub stats).

Credentials stay server-side only (never exposed to the frontend).

Auth options (first match wins):
1. COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET (OIDC client credentials — preferred for SH API)
2. COPERNICUS_USERNAME + COPERNICUS_PASSWORD (password grant via public cdse-public client)
3. COPERNICUS_REFRESH_TOKEN

STAC search does not require auth. Index aggregation uses CDSE Sentinel Hub
Statistical API (openEO rejects many CDSE tokens with TokenInvalid).
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

import httpx

from app.core.config import get_settings
from app.satellite.indices import DISPLAY_RESOLUTION_M, INDEX_FORMULAS, IndexName
from app.satellite.providers.base import (
    IndexCalculationResult,
    IndexStatistics,
    SatelliteImageCandidate,
    SatelliteProviderError,
    VisualizationAsset,
    ZoneIndexResult,
)
from app.satellite.rate_limit import SatelliteRateLimiter, get_satellite_rate_limiter
from app.satellite.zones import build_zone_grid, expand_polygon_meters

logger = logging.getLogger(__name__)

STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
STAC_COLLECTION = "sentinel-2-l2a"
OPENEO_URL = "https://openeo.dataspace.copernicus.eu/openeo/1.2"
SH_STATISTICS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
SH_PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
METERS_PER_DEGREE_LAT = 111_320.0
TARGET_RESOLUTION_M = 10.0
# Display upsample only — Sentinel-2 NDVI/NDRE native info is still ~10 m (NDWI SWIR ~20 m).
VIZ_RESOLUTION_M = DISPLAY_RESOLUTION_M
MAX_VIZ_EDGE_PX = 2048
MIN_VIZ_EDGE_PX = 128


class CopernicusDataSpaceProvider:
    name = "copernicus_cdse"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        limiter: SatelliteRateLimiter | None = None,
        stac_url: str | None = None,
        openeo_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._limiter = limiter or get_satellite_rate_limiter()
        self._stac_url = (stac_url or settings.copernicus_stac_url or STAC_SEARCH_URL).rstrip("/")
        self._openeo_url = (openeo_url or settings.copernicus_openeo_url or OPENEO_URL).rstrip("/")
        self._timeout = httpx.Timeout(settings.satellite_http_timeout_seconds)
        self._token: str | None = None
        self._token_expires_at = 0.0

    def search_available_images(
        self,
        parcel_geometry: dict[str, Any],
        start_date: date,
        end_date: date,
        max_cloud_cover: float,
    ) -> list[SatelliteImageCandidate]:
        body = {
            "collections": [STAC_COLLECTION],
            "datetime": f"{start_date.isoformat()}T00:00:00Z/{end_date.isoformat()}T23:59:59Z",
            "intersects": parcel_geometry,
            "limit": 100,
            "filter-lang": "cql2-json",
            "filter": {
                "op": "<=",
                "args": [{"property": "eo:cloud_cover"}, max_cloud_cover],
            },
        }
        response = self._request("POST", self._stac_url, json=body, auth=False)
        payload = response.json()
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise SatelliteProviderError("STAC search returned malformed payload", retryable=True)
        results: list[SatelliteImageCandidate] = []
        for feature in features:
            candidate = _candidate_from_stac(feature)
            if candidate is not None:
                results.append(candidate)
        results.sort(key=lambda item: item.acquisition_date, reverse=True)
        return results

    def get_image_metadata(self, image_id: str) -> SatelliteImageCandidate:
        url = f"https://stac.dataspace.copernicus.eu/v1/collections/{STAC_COLLECTION}/items/{image_id}"
        response = self._request("GET", url, auth=False)
        if response.status_code == 404:
            raise SatelliteProviderError(f"Image not found: {image_id}", retryable=False, code="not_found")
        candidate = _candidate_from_stac(response.json())
        if candidate is None:
            raise SatelliteProviderError(f"Invalid STAC item: {image_id}", retryable=False)
        return candidate

    def calculate_indices(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        indices: Sequence[IndexName],
        *,
        zone_geometries: Sequence[tuple[str, dict[str, Any]]] | None = None,
    ) -> IndexCalculationResult:
        meta = self.get_image_metadata(image_id)
        zones = list(zone_geometries) if zone_geometries else build_zone_grid(parcel_geometry)
        wanted = list(indices) or [IndexName.NDVI, IndexName.NDRE, IndexName.NDWI]

        parcel_stats: dict[str, IndexStatistics] = {}
        for index in wanted:
            parcel_stats[index.value] = self._aggregate_index(
                parcel_geometry, meta, index
            )

        # Per-zone aggregates for NDVI/NDRE/NDWI so map click inspect has local values
        # for every index (same grid, same method as parcel stats).
        zone_results: list[ZoneIndexResult] = []
        empty = IndexStatistics(mean=None, min=None, max=None, valid_pixel_count=0)
        zone_index_list = [IndexName.NDVI, IndexName.NDRE, IndexName.NDWI]
        for zone_key, geom in zones:
            zone_stats: dict[str, IndexStatistics] = {}
            for index in zone_index_list:
                try:
                    zone_stats[index.value] = self._aggregate_index(geom, meta, index)
                except SatelliteProviderError:
                    zone_stats[index.value] = empty
            zone_results.append(
                ZoneIndexResult(
                    zone_key=zone_key,
                    geometry=geom,
                    ndvi=zone_stats.get(IndexName.NDVI.value, empty),
                    ndre=zone_stats.get(IndexName.NDRE.value, empty),
                    ndwi=zone_stats.get(IndexName.NDWI.value, empty),
                )
            )

        return IndexCalculationResult(
            image_id=meta.image_id,
            product_id=meta.product_id,
            acquisition_date=meta.acquisition_date,
            acquisition_at=meta.acquisition_at,
            cloud_cover=meta.cloud_cover,
            satellite=meta.satellite,
            ndvi=parcel_stats.get(IndexName.NDVI.value, empty),
            ndre=parcel_stats.get(IndexName.NDRE.value, empty),
            ndwi=parcel_stats.get(IndexName.NDWI.value, empty),
            zones=tuple(zone_results),
            image_reference=meta.product_id,
            metadata={
                "provider": self.name,
                "formulas": INDEX_FORMULAS,
                "collection": STAC_COLLECTION,
                "zone_indices": [item.value for item in zone_index_list],
            },
        )

    def get_visualization(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        index: IndexName,
    ) -> VisualizationAsset:
        """Render a georeferenced index PNG clipped to the parcel via Sentinel Hub Process API."""
        meta = self.get_image_metadata(image_id)
        bands, formula = _index_process_parts(index)
        # Slightly expand sampling geometry so edge pixels at the true boundary are filled;
        # the frontend still clips the overlay to the exact parcel outline.
        sample_geometry = expand_polygon_meters(parcel_geometry, meters=20.0)
        extent = _spatial_extent(sample_geometry)
        west, south, east, north = extent["west"], extent["south"], extent["east"], extent["north"]
        width, height = _output_size_px(west, south, east, north)
        start = meta.acquisition_date
        end = start + timedelta(days=1)
        time_from = f"{start.isoformat()}T00:00:00Z"
        time_to = f"{end.isoformat()}T00:00:00Z"
        payload = {
            "input": {
                "bounds": {
                    "bbox": [west, south, east, north],
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
                    },
                    "geometry": sample_geometry,
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {"from": time_from, "to": time_to},
                            "maxCloudCoverage": 100,
                        },
                        # Bilinear so NDRE/NDWI (native ~20 m bands) match NDVI visual grain
                        # when rendered on the same display grid — not a claim of higher native res.
                        "processing": {
                            "harmonizeValues": False,
                            "upsampling": "BILINEAR",
                            "downsampling": "BILINEAR",
                        },
                    }
                ],
            },
            "output": {
                "width": width,
                "height": height,
                "responses": [
                    {
                        "identifier": "default",
                        "format": {"type": "image/png"},
                    }
                ],
            },
            "evalscript": _evalscript_index_rgba(index, formula[0], formula[1], bands),
        }
        response = self._request(
            "POST",
            SH_PROCESS_URL,
            json=payload,
            auth=True,
            headers={"Accept": "image/png"},
        )
        content = response.content
        if not content or len(content) < 32:
            raise SatelliteProviderError(
                "Sentinel Hub Process returned empty visualization",
                code="malformed",
            )
        return VisualizationAsset(
            index=index,
            content_type="image/png",
            content=content,
            width=width,
            height=height,
            bbox=(west, south, east, north),
        )

    def get_statistics(
        self,
        parcel_geometry: dict[str, Any],
        image_id: str,
        index: IndexName,
    ) -> IndexStatistics:
        meta = self.get_image_metadata(image_id)
        return self._aggregate_index(parcel_geometry, meta, index)

    def _aggregate_index(
        self,
        geometry: dict[str, Any],
        meta: SatelliteImageCandidate,
        index: IndexName,
    ) -> IndexStatistics:
        _bands, formula = _index_process_parts(index)
        start = meta.acquisition_date
        end = start + timedelta(days=1)
        time_from = f"{start.isoformat()}T00:00:00Z"
        time_to = f"{end.isoformat()}T00:00:00Z"
        res_deg = TARGET_RESOLUTION_M / METERS_PER_DEGREE_LAT
        payload = {
            "input": {
                "bounds": {"geometry": geometry},
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {"from": time_from, "to": time_to},
                            "maxCloudCoverage": 100,
                        },
                        "processing": {"harmonizeValues": False},
                    }
                ],
            },
            "aggregation": {
                "timeRange": {"from": time_from, "to": time_to},
                "aggregationInterval": {"of": "P1D"},
                "evalscript": _evalscript_normalized_difference(formula[0], formula[1]),
                "resx": res_deg,
                "resy": res_deg,
            },
            "calculations": {"default": {"statistics": {"default": {}}}},
        }
        response = self._request(
            "POST",
            SH_STATISTICS_URL,
            json=payload,
            auth=True,
            headers={"Accept": "application/json"},
        )
        return _parse_statistics_response(response)

    def _request(
        self,
        method: str,
        url: str,
        *,
        auth: bool,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        if not self._limiter.wait_acquire(timeout=90):
            raise SatelliteProviderError("Satellite provider rate limited", code="rate_limited")
        req_headers = {"User-Agent": get_settings().yr_user_agent, "Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        if auth:
            req_headers["Authorization"] = f"Bearer {self._access_token()}"
        try:
            response = self._http(method, url, json=json, headers=req_headers)
        except httpx.TimeoutException as exc:
            raise SatelliteProviderError("Satellite provider timeout", code="timeout") from exc
        except httpx.HTTPError as exc:
            raise SatelliteProviderError("Satellite provider network error", code="network") from exc
        if response.status_code == 429:
            self._limiter.note_rate_limit()
            raise SatelliteProviderError("Satellite provider rate limited", code="rate_limited")
        if response.status_code in {401, 403}:
            self._token = None
            detail = (response.text or "").strip()[:300]
            raise SatelliteProviderError(
                "Copernicus/openEO odbio zahtev (401/403). "
                "Proverite da je OIDC klijent sa CDSE portala (ne Sentinel Hub), "
                "da ima pristup openEO-u i da nalog ima kredite. "
                f"Detalj: {detail or 'bez tela odgovora'}",
                retryable=False,
                code="auth_failed",
            )
        if response.status_code >= 500:
            raise SatelliteProviderError(
                f"Satellite provider error ({response.status_code})",
                code="provider_error",
            )
        if response.status_code >= 400:
            detail = response.text[:400]
            raise SatelliteProviderError(
                f"Satellite provider rejected request ({response.status_code}): {detail}",
                retryable=response.status_code >= 500,
                code="provider_error",
            )
        self._limiter.note_success()
        return response

    def _http(
        self,
        method: str,
        url: str,
        *,
        json: dict | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            return self._client.request(method, url, json=json, headers=headers)
        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            return client.request(method, url, json=json, headers=headers)

    def _access_token(self) -> str:
        import time

        settings = get_settings()
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token
        data: dict[str, str]
        if settings.copernicus_client_id and settings.copernicus_client_secret:
            data = {
                "grant_type": "client_credentials",
                "client_id": settings.copernicus_client_id,
                "client_secret": settings.copernicus_client_secret,
            }
        elif settings.copernicus_username and settings.copernicus_password:
            # Public browser client — confidential sh-… clients reject password grant.
            data = {
                "grant_type": "password",
                "client_id": "cdse-public",
                "username": settings.copernicus_username,
                "password": settings.copernicus_password,
            }
        elif settings.copernicus_refresh_token:
            data = {
                "grant_type": "refresh_token",
                "client_id": "cdse-public",
                "refresh_token": settings.copernicus_refresh_token,
            }
        else:
            raise SatelliteProviderError(
                "Copernicus credentials are not configured",
                retryable=False,
                code="missing_credentials",
            )
        try:
            if self._client is not None:
                response = self._client.post(TOKEN_URL, data=data)
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(TOKEN_URL, data=data)
        except httpx.HTTPError as exc:
            raise SatelliteProviderError("Failed to obtain Copernicus token", code="auth_failed") from exc
        if response.status_code >= 400:
            detail = (response.text or "").strip()[:300]
            raise SatelliteProviderError(
                f"Neuspelo dobijanje Copernicus tokena ({response.status_code}): {detail}",
                retryable=False,
                code="auth_failed",
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise SatelliteProviderError("Copernicus token response missing access_token", retryable=False)
        expires_in = float(payload.get("expires_in") or 600)
        self._token = str(token)
        self._token_expires_at = now + expires_in
        return self._token


def _index_process_parts(index: IndexName) -> tuple[list[str], tuple[str, str]]:
    """Return (bands, (numerator_band, denominator_band)) for normalized_difference."""
    settings = get_settings()
    if index == IndexName.NDVI:
        return ["B04", "B08"], ("B08", "B04")
    if index == IndexName.NDRE:
        nir = settings.satellite_ndre_nir_band or "B8A"
        red_edge = settings.satellite_ndre_red_edge_band or "B05"
        return [red_edge, nir], (nir, red_edge)
    # NDWI_GAO
    return ["B08", "B11"], ("B08", "B11")


def _spatial_extent(geometry: dict[str, Any]) -> dict[str, float]:
    from app.satellite.zones import parcel_bbox

    west, south, east, north = parcel_bbox(geometry)
    pad = 0.0002
    return {
        "west": west - pad,
        "south": south - pad,
        "east": east + pad,
        "north": north + pad,
    }


def _output_size_px(west: float, south: float, east: float, north: float) -> tuple[int, int]:
    mid_lat = (south + north) / 2.0
    width_m = max((east - west) * METERS_PER_DEGREE_LAT * max(math.cos(math.radians(mid_lat)), 0.2), 20.0)
    height_m = max((north - south) * METERS_PER_DEGREE_LAT, 20.0)
    width = int(round(width_m / VIZ_RESOLUTION_M))
    height = int(round(height_m / VIZ_RESOLUTION_M))
    width = max(MIN_VIZ_EDGE_PX, min(MAX_VIZ_EDGE_PX, width))
    height = max(MIN_VIZ_EDGE_PX, min(MAX_VIZ_EDGE_PX, height))
    return width, height


# Per-index display stretch (vmin, vmax). Same palette, different value mapping.
INDEX_COLOR_STRETCH: dict[IndexName, tuple[float, float]] = {
    IndexName.NDVI: (-0.2, 0.9),
    IndexName.NDRE: (-0.1, 0.6),
    IndexName.NDWI: (-0.5, 0.2),
}


def _evalscript_index_rgba(
    index: IndexName,
    numerator: str,
    denominator: str,
    bands: list[str],
) -> str:
    """RGBA PNG: red→yellow→green colormap with index-specific stretch, transparent outside parcel."""
    unique = list(dict.fromkeys([*bands, "dataMask"]))
    band_list = ", ".join(f'"{b}"' for b in unique)
    vmin, vmax = INDEX_COLOR_STRETCH.get(index, (-0.2, 0.9))
    span = max(vmax - vmin, 1e-6)
    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{bands: [{band_list}], units: "REFLECTANCE"}}],
    output: {{ bands: 4, sampleType: "UINT8" }}
  }};
}}
function evaluatePixel(sample) {{
  // dataMask is 0 outside the request geometry / no-data → transparent PNG alpha.
  if (!sample.dataMask) {{
    return [0, 0, 0, 0];
  }}
  let x = sample.{numerator};
  let y = sample.{denominator};
  let denom = x + y;
  if (denom === 0) {{
    return [0, 0, 0, 0];
  }}
  let value = (x - y) / denom;
  // Map [{vmin}, {vmax}] → [0, 1] then red (low) → yellow → green (high).
  let t = Math.max(0, Math.min(1, (value - ({vmin})) / ({span})));
  let r;
  let g;
  let b;
  if (t < 0.5) {{
    let u = t / 0.5;
    r = 215;
    g = Math.round(35 + 185 * u);
    b = 25;
  }} else {{
    let u = (t - 0.5) / 0.5;
    r = Math.round(215 - 175 * u);
    g = Math.round(220 - 55 * u);
    b = Math.round(25 + 35 * u);
  }}
  // UINT8 alpha: 255 opaque inside parcel (dataMask is 0|1).
  return [r, g, b, 255 * sample.dataMask];
}}
"""


def _candidate_from_stac(feature: Any) -> SatelliteImageCandidate | None:
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties") or {}
    image_id = str(feature.get("id") or "")
    if not image_id:
        return None
    raw_dt = props.get("datetime") or props.get("start_datetime")
    acquisition_at = _parse_dt(raw_dt)
    acquisition_date = acquisition_at.date() if acquisition_at else None
    if acquisition_date is None:
        return None
    cloud = props.get("eo:cloud_cover")
    try:
        cloud_cover = float(cloud) if cloud is not None else None
    except (TypeError, ValueError):
        cloud_cover = None
    return SatelliteImageCandidate(
        image_id=image_id,
        product_id=image_id,
        acquisition_date=acquisition_date,
        acquisition_at=acquisition_at,
        cloud_cover=cloud_cover,
        satellite="Sentinel-2",
        collection=STAC_COLLECTION,
        metadata={"stac_properties": props},
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _evalscript_normalized_difference(numerator: str, denominator: str) -> str:
    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{bands: ["{numerator}", "{denominator}", "dataMask"], units: "REFLECTANCE"}}],
    output: [
      {{ id: "default", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "dataMask", bands: 1 }}
    ]
  }};
}}
function evaluatePixel(samples) {{
  let x = samples.{numerator};
  let y = samples.{denominator};
  let value = (x - y) / (x + y);
  return {{ default: [value], dataMask: [samples.dataMask] }};
}}
"""


def _parse_statistics_response(response: httpx.Response) -> IndexStatistics:
    """Parse CDSE Sentinel Hub Statistical API JSON into IndexStatistics."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise SatelliteProviderError("Failed to parse Sentinel Hub statistics", code="malformed") from exc
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        return IndexStatistics(mean=None, min=None, max=None, valid_pixel_count=0)
    outputs = rows[0].get("outputs") if isinstance(rows[0], dict) else None
    default = outputs.get("default") if isinstance(outputs, dict) else None
    bands = default.get("bands") if isinstance(default, dict) else None
    band0 = bands.get("B0") if isinstance(bands, dict) else None
    stats = band0.get("stats") if isinstance(band0, dict) else None
    if not isinstance(stats, dict):
        return IndexStatistics(mean=None, min=None, max=None, valid_pixel_count=0)
    mean = _finite_float(stats.get("mean"))
    minimum = _finite_float(stats.get("min"))
    maximum = _finite_float(stats.get("max"))
    stddev = _finite_float(stats.get("stDev"))
    sample_count = int(stats.get("sampleCount") or 0)
    no_data = int(stats.get("noDataCount") or 0)
    valid = max(sample_count - no_data, 0)
    if mean is None:
        return IndexStatistics(mean=None, min=None, max=None, valid_pixel_count=valid)
    return IndexStatistics(
        mean=mean,
        min=minimum if minimum is not None else mean,
        max=maximum if maximum is not None else mean,
        stddev=stddev,
        valid_pixel_count=valid,
    )


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number
