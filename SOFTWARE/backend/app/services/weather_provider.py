from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.weather_calc import yr_coordinate

YR_COMPACT_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


class YrWeatherError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


@dataclass
class YrFetchResult:
    payload: dict[str, Any] | None
    not_modified: bool
    last_modified: str | None
    expires_at: datetime | None
    source_updated_at: datetime | None


class YrWeatherProvider:
    def __init__(self, client: httpx.Client | None = None, user_agent: str | None = None) -> None:
        settings = get_settings()
        self._client = client
        self._user_agent = (user_agent or settings.yr_user_agent).strip()
        self._timeout = httpx.Timeout(15.0)

    def fetch(
        self,
        latitude: Decimal | float,
        longitude: Decimal | float,
        last_modified: str | None = None,
    ) -> YrFetchResult:
        if not self._user_agent:
            raise YrWeatherError(403, "missing_user_agent")
        lat = f"{yr_coordinate(latitude):.4f}"
        lon = f"{yr_coordinate(longitude):.4f}"
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
        }
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        try:
            response = self._request(lat, lon, headers)
        except httpx.HTTPError as exc:
            raise YrWeatherError(0, "network") from exc
        return self._parse_response(response)

    def _request(self, lat: str, lon: str, headers: dict[str, str]) -> httpx.Response:
        params = {"lat": lat, "lon": lon}
        if self._client is not None:
            return self._client.get(YR_COMPACT_URL, params=params, headers=headers)
        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            return client.get(YR_COMPACT_URL, params=params, headers=headers)

    def _parse_response(self, response: httpx.Response) -> YrFetchResult:
        status = response.status_code
        last_modified = response.headers.get("Last-Modified")
        expires_at = _parse_http_datetime(response.headers.get("Expires"))
        if status == 304:
            return YrFetchResult(
                payload=None,
                not_modified=True,
                last_modified=last_modified,
                expires_at=expires_at,
                source_updated_at=None,
            )
        if status == 200:
            try:
                payload = response.json()
            except ValueError as exc:
                raise YrWeatherError(200, "invalid_json") from exc
            if not isinstance(payload, dict):
                raise YrWeatherError(200, "invalid_json")
            source_updated_at = _source_updated_at(payload)
            return YrFetchResult(
                payload=payload,
                not_modified=False,
                last_modified=last_modified,
                expires_at=expires_at,
                source_updated_at=source_updated_at,
            )
        if status in {403, 404, 429} or status >= 500:
            raise YrWeatherError(status, "provider_error")
        raise YrWeatherError(status, "provider_error")


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _source_updated_at(payload: dict[str, Any]) -> datetime | None:
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        return None
    meta = properties.get("meta")
    if not isinstance(meta, dict):
        return None
    raw = meta.get("updated_at")
    if not isinstance(raw, str):
        return None
    try:
        from app.services.weather_calc import parse_utc

        return parse_utc(raw)
    except ValueError:
        return None
