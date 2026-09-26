from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.parcel import Parcel
from app.models.soil import SoilProfileSnapshot
from app.repositories.parcel import ParcelRepository
from app.repositories.soil import SoilProfileRepository
from app.schemas.soil import ParcelSoilProfileRead, SoilDepthValueRead, SoilPropertyRead
from app.soil.properties import (
    DATASET_VERSION,
    PROPERTY_SPECS,
    PROVIDER_NAME,
    SOURCE_EXPLANATION,
    SOURCE_LABEL,
    SOURCE_TYPE,
    SPATIAL_RESOLUTION,
    SUPPORTED_DEPTHS,
    ParseResult,
    coordinates_are_valid,
    depth_label,
    parse_soilgrids_payload,
    soil_coordinate,
    stored_depth_value,
)
from app.soil.provider import SoilGridsError, SoilGridsProvider

_LOCATION_REQUIRED = "Lokacija parcele nije podešena."
_UNAVAILABLE = "Podaci o zemljištu trenutno nisu dostupni."
_RATE_LIMITED = "Podaci trenutno nisu dostupni. Pokušajte ponovo kasnije."
_TIMEOUT = "Zahtev ka SoilGrids je istekao."
_MALFORMED = "Odgovor SoilGrids servisa nije mogao da se obradi."
_PARTIAL = "Neki parametri nisu dostupni za ovu lokaciju."
_STALE = "Podaci su stariji od predviđenog perioda i biće osveženi."
_REFRESH_LIMITED = "Osvežavanje je privremeno ograničeno zbog SoilGrids ograničenja."

_locks_guard = threading.Lock()
_parcel_locks: dict[str, threading.Lock] = {}

_ERROR_MESSAGES = {
    "rate_limited": _RATE_LIMITED,
    "timeout": _TIMEOUT,
    "malformed": _MALFORMED,
    "unavailable": _UNAVAILABLE,
}


class SoilService:
    def __init__(self, db: Session, provider: SoilGridsProvider | None = None) -> None:
        self.db = db
        self.parcels = ParcelRepository(db)
        self.snapshots = SoilProfileRepository(db)
        self.provider = provider or SoilGridsProvider()
        settings = get_settings()
        self.cache_ttl = timedelta(days=settings.soilgrids_cache_days)
        self.min_refresh = timedelta(seconds=settings.soilgrids_min_refresh_seconds)

    def get_profile(self, owner_id: UUID, parcel_id: UUID) -> ParcelSoilProfileRead:
        return self._profile(owner_id, parcel_id, force_refresh=False)

    def refresh_profile(self, owner_id: UUID, parcel_id: UUID) -> ParcelSoilProfileRead:
        return self._profile(owner_id, parcel_id, force_refresh=True)

    def _profile(self, owner_id: UUID, parcel_id: UUID, *, force_refresh: bool) -> ParcelSoilProfileRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        if not coordinates_are_valid(parcel.latitude, parcel.longitude):
            return self._empty(parcel, "location_required", _LOCATION_REQUIRED)

        lock = _lock_for(parcel.id)
        with lock:
            return self._profile_locked(parcel, force_refresh=force_refresh)

    def _profile_locked(self, parcel: Parcel, *, force_refresh: bool) -> ParcelSoilProfileRead:
        assert parcel.latitude is not None and parcel.longitude is not None
        now = datetime.now(timezone.utc)
        snapshot = self.snapshots.get_for_parcel(parcel.id)
        location_match = snapshot is not None and self._snapshot_matches_location(snapshot, parcel)

        if location_match and snapshot is not None:
            if force_refresh and not self._refresh_allowed(snapshot, now):
                return self._from_snapshot(parcel, snapshot, stale=False, message=_REFRESH_LIMITED)
            if not force_refresh and self._snapshot_is_fresh(snapshot, now):
                return self._from_snapshot(parcel, snapshot, stale=False)

        try:
            result = self.provider.fetch(parcel.latitude, parcel.longitude)
        except SoilGridsError as exc:
            if location_match and snapshot is not None:
                return self._from_snapshot(parcel, snapshot, stale=True, message=_STALE)
            return self._empty(parcel, _status_for_error(exc.code), _ERROR_MESSAGES.get(exc.code, _UNAVAILABLE))

        parsed = parse_soilgrids_payload(result.payload)
        if parsed.status == "malformed":
            if location_match and snapshot is not None:
                return self._from_snapshot(parcel, snapshot, stale=True, message=_STALE)
            return self._empty(parcel, "malformed", _MALFORMED)

        try:
            snapshot = self._store(parcel, snapshot, result.payload, parsed, result.dataset_version, now)
        except Exception:
            self.db.rollback()
            if location_match and snapshot is not None:
                return self._from_snapshot(parcel, snapshot, stale=True, message=_STALE)
            return self._empty(parcel, "unavailable", _UNAVAILABLE)

        return self._from_snapshot(parcel, snapshot, stale=False)

    def _store(
        self,
        parcel: Parcel,
        snapshot: SoilProfileSnapshot | None,
        raw_payload: dict[str, Any],
        parsed: ParseResult,
        dataset_version: str,
        now: datetime,
    ) -> SoilProfileSnapshot:
        metadata = {
            "source_type": SOURCE_TYPE,
            "source_label": SOURCE_LABEL,
            "unit_measures": parsed.unit_measures,
            "query": {
                "lat": float(soil_coordinate(parcel.latitude)),
                "lon": float(soil_coordinate(parcel.longitude)),
                "dataset_version": dataset_version or DATASET_VERSION,
            },
            "geometry": raw_payload.get("geometry") if isinstance(raw_payload.get("geometry"), dict) else None,
        }
        message = _PARTIAL if parsed.status == "partial" else None
        expires_at = now + self.cache_ttl
        if snapshot is None:
            snapshot = SoilProfileSnapshot(
                parcel_id=parcel.id,
                provider=PROVIDER_NAME,
                dataset_version=dataset_version or DATASET_VERSION,
                latitude=parcel.latitude,
                longitude=parcel.longitude,
                fetched_at=now,
                expires_at=expires_at,
                source_metadata=metadata,
                values=parsed.values_payload,
                status=parsed.status,
                message=message,
                missing_properties=parsed.missing_properties,
            )
            self.snapshots.add(snapshot)
        else:
            snapshot.provider = PROVIDER_NAME
            snapshot.dataset_version = dataset_version or DATASET_VERSION
            snapshot.latitude = parcel.latitude
            snapshot.longitude = parcel.longitude
            snapshot.fetched_at = now
            snapshot.expires_at = expires_at
            snapshot.source_metadata = metadata
            snapshot.values = parsed.values_payload
            snapshot.status = parsed.status
            snapshot.message = message
            snapshot.missing_properties = parsed.missing_properties
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def _snapshot_matches_location(self, snapshot: SoilProfileSnapshot, parcel: Parcel) -> bool:
        if snapshot.dataset_version != DATASET_VERSION:
            return False
        return _same_coords(snapshot.latitude, snapshot.longitude, parcel.latitude, parcel.longitude)

    def _snapshot_is_fresh(self, snapshot: SoilProfileSnapshot, now: datetime) -> bool:
        fetched = _as_utc(snapshot.fetched_at)
        expires = _as_utc(snapshot.expires_at)
        if expires is not None and now < expires:
            return True
        if fetched is None:
            return False
        return now - fetched < self.cache_ttl

    def _refresh_allowed(self, snapshot: SoilProfileSnapshot, now: datetime) -> bool:
        fetched = _as_utc(snapshot.fetched_at)
        if fetched is None:
            return True
        return now - fetched >= self.min_refresh

    def _from_snapshot(
        self,
        parcel: Parcel,
        snapshot: SoilProfileSnapshot,
        *,
        stale: bool,
        message: str | None = None,
    ) -> ParcelSoilProfileRead:
        now = datetime.now(timezone.utc)
        properties = _properties_from_values(snapshot.values, snapshot.fetched_at)
        missing = [item for item in snapshot.missing_properties if isinstance(item, str)]
        if stale:
            status = "stale"
            text = message or _STALE
        elif snapshot.status == "partial" or missing:
            status = "partial"
            text = message or snapshot.message or _PARTIAL
        else:
            status = "ok"
            text = message
        can_refresh = self._refresh_allowed(snapshot, now)
        refresh_at = None if can_refresh else (_as_utc(snapshot.fetched_at) or now) + self.min_refresh
        return ParcelSoilProfileRead(
            available=True,
            status=status,  # type: ignore[arg-type]
            is_stale=stale,
            message=text,
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            latitude=float(soil_coordinate(parcel.latitude)) if parcel.latitude is not None else None,
            longitude=float(soil_coordinate(parcel.longitude)) if parcel.longitude is not None else None,
            provider=PROVIDER_NAME,
            source=PROVIDER_NAME,
            source_type=SOURCE_TYPE,
            source_label=SOURCE_LABEL,
            source_explanation=SOURCE_EXPLANATION,
            dataset_version=snapshot.dataset_version,
            spatial_resolution=SPATIAL_RESOLUTION,
            fetched_at=snapshot.fetched_at,
            generated_at=snapshot.fetched_at,
            is_modeled=True,
            can_refresh=can_refresh,
            refresh_available_at=refresh_at,
            depths=_available_depths(properties),
            properties=properties,
            missing_properties=missing,
        )

    def _empty(self, parcel: Parcel, status: str, message: str) -> ParcelSoilProfileRead:
        latitude = float(soil_coordinate(parcel.latitude)) if parcel.latitude is not None else None
        longitude = float(soil_coordinate(parcel.longitude)) if parcel.longitude is not None else None
        return ParcelSoilProfileRead(
            available=False,
            status=status,  # type: ignore[arg-type]
            is_stale=False,
            message=message,
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            latitude=latitude,
            longitude=longitude,
            provider=PROVIDER_NAME,
            source=PROVIDER_NAME,
            source_type=SOURCE_TYPE,
            source_label=SOURCE_LABEL,
            source_explanation=SOURCE_EXPLANATION,
            dataset_version=DATASET_VERSION,
            spatial_resolution=SPATIAL_RESOLUTION,
            fetched_at=None,
            generated_at=None,
            is_modeled=True,
            can_refresh=False,
            refresh_available_at=None,
            depths=list(SUPPORTED_DEPTHS),
            properties=[],
            missing_properties=[spec.key for spec in PROPERTY_SPECS],
        )


def _lock_for(parcel_id: UUID) -> threading.Lock:
    key = str(parcel_id)
    with _locks_guard:
        lock = _parcel_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _parcel_locks[key] = lock
        return lock


def _same_coords(
    cached_lat: Decimal,
    cached_lon: Decimal,
    parcel_lat: Decimal | None,
    parcel_lon: Decimal | None,
) -> bool:
    if parcel_lat is None or parcel_lon is None:
        return False
    return soil_coordinate(cached_lat) == soil_coordinate(parcel_lat) and soil_coordinate(cached_lon) == soil_coordinate(
        parcel_lon
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _status_for_error(code: str) -> str:
    if code in {"rate_limited", "timeout", "malformed"}:
        return code
    return "unavailable"


def _properties_from_values(payload: dict[str, Any] | None, generated_at: datetime | None) -> list[SoilPropertyRead]:
    stored = payload if isinstance(payload, dict) else {}
    result: list[SoilPropertyRead] = []
    for spec in PROPERTY_SPECS:
        raw_depths = stored.get(spec.key)
        depths: list[SoilDepthValueRead] = []
        if isinstance(raw_depths, dict):
            for depth_key in spec_depth_order(raw_depths):
                parsed = stored_depth_value(raw_depths[depth_key])
                if parsed is None:
                    continue
                depths.append(
                    SoilDepthValueRead(
                        depth=depth_key,
                        depth_label=depth_label(depth_key),
                        value=parsed.value,
                        unit=parsed.unit or spec.display_unit,
                        uncertainty=parsed.uncertainty,
                        lower=parsed.lower,
                        upper=parsed.upper,
                    )
                )
        surface = depths[0] if depths else None
        result.append(
            SoilPropertyRead(
                key=spec.key,
                label=spec.label,
                unit=spec.display_unit,
                value=surface.value if surface else None,
                depth=surface.depth if surface else None,
                depth_label=surface.depth_label if surface else None,
                source=PROVIDER_NAME,
                source_type=SOURCE_TYPE,
                source_label=SOURCE_LABEL,
                measured_at=None,
                generated_at=generated_at,
                is_modeled=True,
                available=bool(depths),
                depths=depths,
            )
        )
    return result


def spec_depth_order(raw_depths: dict[str, Any]) -> list[str]:
    ordered = [key for key in SUPPORTED_DEPTHS if key in raw_depths]
    extras = [key for key in raw_depths if key not in ordered]
    return ordered + extras


def _available_depths(properties: list[SoilPropertyRead]) -> list[str]:
    seen: list[str] = []
    for depth_key in SUPPORTED_DEPTHS:
        if any(item.depth == depth_key for prop in properties for item in prop.depths):
            seen.append(depth_key)
    extras = [
        item.depth
        for prop in properties
        for item in prop.depths
        if item.depth not in seen
    ]
    for extra in extras:
        if extra not in seen:
            seen.append(extra)
    return seen
