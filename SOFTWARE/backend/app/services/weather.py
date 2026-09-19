from __future__ import annotations

import threading
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.maps import coordinates_as_decimal, resolve_maps_location
from app.core.exceptions import NotFoundError
from app.models.parcel import Parcel
from app.models.weather import WeatherForecastCache
from app.repositories.parcel import ParcelRepository
from app.repositories.weather import WeatherCacheRepository
from app.schemas.weather import DailyForecastRead, ParcelWeatherRead
from app.services.weather_calc import (
    DEFAULT_TIMEZONE,
    daily_forecast_to_dict,
    normalize_compact_forecast,
    yr_coordinate,
)
from app.services.weather_provider import YrFetchResult, YrWeatherError, YrWeatherProvider

_NO_LOCATION = "Za prikaz prognoze potrebno je da parcela ima definisanu lokaciju."
_INVALID_LOCATION = "Lokacija parcele nije mogla da se odredi. Izmenite Google Maps link parcele."
_UNAVAILABLE = "Vremenska prognoza trenutno nije dostupna."

_locks_guard = threading.Lock()
_parcel_locks: dict[str, threading.Lock] = {}


class WeatherService:
    def __init__(self, db: Session, provider: YrWeatherProvider | None = None) -> None:
        self.db = db
        self.parcels = ParcelRepository(db)
        self.cache = WeatherCacheRepository(db)
        self.provider = provider or YrWeatherProvider()

    def get_forecast(self, owner_id: UUID, parcel_id: UUID) -> ParcelWeatherRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")

        timezone_name = DEFAULT_TIMEZONE
        resolved = self._ensure_coordinates(parcel)
        if resolved == "missing":
            return self._empty(parcel, "no_location", _NO_LOCATION, timezone_name)
        if resolved == "invalid":
            return self._empty(parcel, "invalid_location", _INVALID_LOCATION, timezone_name)

        lock = _lock_for(parcel.id)
        with lock:
            return self._forecast_locked(parcel, timezone_name)

    def _forecast_locked(self, parcel: Parcel, timezone_name: str) -> ParcelWeatherRead:
        assert parcel.latitude is not None and parcel.longitude is not None
        today = datetime.now(ZoneInfo(timezone_name)).date()
        cache = self.cache.get_for_parcel(parcel.id)
        if cache is not None and self._cache_is_fresh(cache, parcel, today):
            return self._from_cache(parcel, cache, timezone_name, stale=False)

        try:
            result = self.provider.fetch(parcel.latitude, parcel.longitude, cache.last_modified if cache else None)
        except YrWeatherError:
            if cache is not None:
                return self._from_cache(parcel, cache, timezone_name, stale=True)
            return self._empty(parcel, "unavailable", _UNAVAILABLE, timezone_name)

        try:
            cache = self._store_result(parcel, cache, result, timezone_name, today)
        except Exception:
            self.db.rollback()
            if cache is not None:
                return self._from_cache(parcel, cache, timezone_name, stale=True)
            return self._empty(parcel, "unavailable", _UNAVAILABLE, timezone_name)

        return self._from_cache(parcel, cache, timezone_name, stale=False)

    def _ensure_coordinates(self, parcel: Parcel) -> str:
        if parcel.latitude is not None and parcel.longitude is not None:
            return "ok"
        if not parcel.maps_url:
            return "missing"
        try:
            location = resolve_maps_location(parcel.maps_url, fallback_query=parcel.name)
        except Exception:
            location = None
        if location is None:
            return "invalid"
        parcel.latitude, parcel.longitude = coordinates_as_decimal(location)
        self.db.commit()
        self.db.refresh(parcel)
        return "ok"

    def _cache_is_fresh(self, cache: WeatherForecastCache, parcel: Parcel, today) -> bool:
        if cache.forecast_date != today:
            return False
        return _same_yr_coords(cache.latitude, cache.longitude, parcel.latitude, parcel.longitude)

    def _store_result(
        self,
        parcel: Parcel,
        cache: WeatherForecastCache | None,
        result: YrFetchResult,
        timezone_name: str,
        today,
    ) -> WeatherForecastCache:
        now = datetime.now(ZoneInfo(timezone_name))
        payload = result.payload
        if result.not_modified and cache is not None:
            payload = cache.raw_response if isinstance(cache.raw_response, dict) else None
            if not payload:
                cache.forecast_date = today
                cache.fetched_at = now
                if result.last_modified:
                    cache.last_modified = result.last_modified
                if result.expires_at is not None:
                    cache.expires_at = result.expires_at
                self.db.commit()
                self.db.refresh(cache)
                return cache

        if payload is None:
            raise YrWeatherError(0, "empty_payload")

        days = normalize_compact_forecast(payload, timezone_name, now=now)
        normalized = {
            "timezone": timezone_name,
            "forecast": [daily_forecast_to_dict(day) for day in days],
        }
        if cache is None:
            cache = WeatherForecastCache(
                parcel_id=parcel.id,
                latitude=parcel.latitude,
                longitude=parcel.longitude,
                provider="yr",
                forecast_date=today,
                fetched_at=now,
                expires_at=result.expires_at,
                source_updated_at=result.source_updated_at,
                last_modified=result.last_modified,
                raw_response=payload,
                normalized_response=normalized,
            )
            self.cache.add(cache)
        else:
            cache.latitude = parcel.latitude
            cache.longitude = parcel.longitude
            cache.provider = "yr"
            cache.forecast_date = today
            cache.fetched_at = now
            if result.expires_at is not None:
                cache.expires_at = result.expires_at
            if result.source_updated_at is not None:
                cache.source_updated_at = result.source_updated_at
            if result.last_modified:
                cache.last_modified = result.last_modified
            cache.raw_response = payload
            cache.normalized_response = normalized
        self.db.commit()
        self.db.refresh(cache)
        return cache

    def _from_cache(
        self,
        parcel: Parcel,
        cache: WeatherForecastCache,
        timezone_name: str,
        *,
        stale: bool,
    ) -> ParcelWeatherRead:
        forecast = _forecast_from_normalized(cache.normalized_response)
        status = "stale" if stale else "ok"
        message = "Prikazani su poslednji dostupni podaci." if stale else None
        return ParcelWeatherRead(
            available=True,
            status=status,
            message=message,
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            latitude=float(yr_coordinate(parcel.latitude)) if parcel.latitude is not None else None,
            longitude=float(yr_coordinate(parcel.longitude)) if parcel.longitude is not None else None,
            timezone=timezone_name,
            forecast=forecast,
            fetched_at=cache.fetched_at,
            source="Yr",
        )

    def _empty(self, parcel: Parcel, status: str, message: str, timezone_name: str) -> ParcelWeatherRead:
        latitude = float(yr_coordinate(parcel.latitude)) if parcel.latitude is not None else None
        longitude = float(yr_coordinate(parcel.longitude)) if parcel.longitude is not None else None
        return ParcelWeatherRead(
            available=False,
            status=status,  # type: ignore[arg-type]
            message=message,
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone_name,
            forecast=[],
            fetched_at=None,
            source="Yr",
        )


def _lock_for(parcel_id: UUID) -> threading.Lock:
    key = str(parcel_id)
    with _locks_guard:
        lock = _parcel_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _parcel_locks[key] = lock
        return lock


def _same_yr_coords(
    cached_lat: Decimal,
    cached_lon: Decimal,
    parcel_lat: Decimal | None,
    parcel_lon: Decimal | None,
) -> bool:
    if parcel_lat is None or parcel_lon is None:
        return False
    return yr_coordinate(cached_lat) == yr_coordinate(parcel_lat) and yr_coordinate(cached_lon) == yr_coordinate(
        parcel_lon
    )


def _forecast_from_normalized(payload: dict[str, Any] | None) -> list[DailyForecastRead]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("forecast")
    if not isinstance(rows, list):
        return []
    result: list[DailyForecastRead] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            result.append(DailyForecastRead.model_validate(item))
        except Exception:
            continue
    return result[:7]
