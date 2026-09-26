from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings
from app.soil.properties import REQUESTED_LAYER_NAMES, SUPPORTED_DEPTHS, soil_coordinate
from app.soil.rate_limit import SoilGridsRateLimiter

SOILGRIDS_QUERY_PATH = "/soilgrids/v2.0/properties/query"
# Quantiles (Q0.05/Q0.95) are parsed when present. The live query is already slow;
# requesting extra stats has caused 60s+ stalls, so the default request asks for
# mean + uncertainty only.
VALUE_STATS = ("mean", "uncertainty")

_default_limiter = SoilGridsRateLimiter()


class SoilGridsError(Exception):
    def __init__(self, status_code: int, code: str, message: str = "") -> None:
        self.status_code = status_code
        self.code = code
        self.message = message or code
        super().__init__(self.message)


@dataclass
class SoilGridsFetchResult:
    payload: dict[str, Any]
    dataset_version: str


class SoilGridsProvider:
    """One HTTP query returns every requested property and depth interval."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        limiter: SoilGridsRateLimiter | None = None,
        base_url: str | None = None,
        user_agent: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._limiter = limiter or _default_limiter
        if limiter is None and settings.soilgrids_min_interval_seconds != _default_limiter.min_interval:
            _default_limiter.min_interval = settings.soilgrids_min_interval_seconds
        self._base_url = (base_url or settings.soilgrids_base_url).rstrip("/")
        self._user_agent = (user_agent or settings.soilgrids_user_agent or settings.yr_user_agent).strip()
        seconds = timeout if timeout is not None else settings.soilgrids_timeout_seconds
        self._timeout = httpx.Timeout(seconds)

    def fetch(self, latitude: Decimal | float, longitude: Decimal | float) -> SoilGridsFetchResult:
        if not self._limiter.acquire():
            raise SoilGridsError(429, "rate_limited")
        headers = {
            "User-Agent": self._user_agent or "AgroTwin/1.0",
            "Accept": "application/json",
        }
        params = _query_params(latitude, longitude)
        url = f"{self._base_url}{SOILGRIDS_QUERY_PATH}"
        try:
            response = self._request(url, params, headers)
        except httpx.TimeoutException as exc:
            raise SoilGridsError(0, "timeout") from exc
        except httpx.HTTPError as exc:
            raise SoilGridsError(0, "unavailable") from exc
        return self._parse_response(response)

    def _request(self, url: str, params: list[tuple[str, str]], headers: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return self._client.get(url, params=params, headers=headers)
        # rest.isric.org can stall on IPv6; curl/IPv4 typically returns in ~30s.
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(timeout=self._timeout, follow_redirects=True, transport=transport) as client:
            return client.get(url, params=params, headers=headers)

    def _parse_response(self, response: httpx.Response) -> SoilGridsFetchResult:
        status = response.status_code
        if status == 429:
            self._limiter.note_rate_limit()
            raise SoilGridsError(429, "rate_limited")
        if status == 408:
            raise SoilGridsError(408, "timeout")
        if status >= 500 or status in {403, 404}:
            raise SoilGridsError(status, "unavailable")
        if status != 200:
            raise SoilGridsError(status, "unavailable")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SoilGridsError(200, "malformed") from exc
        if not isinstance(payload, dict):
            raise SoilGridsError(200, "malformed")
        self._limiter.note_success()
        return SoilGridsFetchResult(payload=payload, dataset_version="2.0")


def reset_default_limiter() -> None:
    _default_limiter.reset()


def _query_params(latitude: Decimal | float, longitude: Decimal | float) -> list[tuple[str, str]]:
    lat = f"{soil_coordinate(latitude):.4f}"
    lon = f"{soil_coordinate(longitude):.4f}"
    params: list[tuple[str, str]] = [("lon", lon), ("lat", lat)]
    for name in REQUESTED_LAYER_NAMES:
        params.append(("property", name))
    for depth in SUPPORTED_DEPTHS:
        params.append(("depth", depth))
    for stat in VALUE_STATS:
        params.append(("value", stat))
    return params
