"""Coverage KPIs over parcels the organization can already read."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enterprise.access import EnterpriseAccess
from app.enterprise.data_quality import SATELLITE_NOTES, business_buckets, satellite_buckets
from app.models.enums import ParcelAlertStatus
from app.models.farm import Farm
from app.models.intelligence import ParcelAlert
from app.models.parcel import Parcel
from app.models.satellite import SatelliteObservation
from app.models.user import User
from app.schemas.enterprise import EnterpriseDataQuality, EnterpriseDataQualityParcel
from app.services.enterprise import EnterpriseService

_OPEN = {ParcelAlertStatus.OPEN, ParcelAlertStatus.ACKNOWLEDGED}


class EnterpriseDataQualityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.access = EnterpriseAccess(db)
        self.enterprise = EnterpriseService(db)

    def summary(
        self,
        user: User,
        organization_id: UUID,
        *,
        year: int | None = None,
        bucket: str | None = None,
    ) -> EnterpriseDataQuality:
        self.access.require_reader(user, organization_id)
        season = year or date.today().year
        start = date(season, 1, 1)
        end = date(season, 12, 31)
        parcel_ids = self.access.readable_parcel_ids(organization_id)
        parcels = (
            list(self.db.scalars(select(Parcel).where(Parcel.id.in_(parcel_ids))).all())
            if parcel_ids
            else []
        )
        observations = self._observations(parcel_ids, start, end)
        open_parcels = self._open_alert_parcels(parcel_ids)
        classified: list[tuple[Parcel, set[str]]] = []
        for parcel in parcels:
            buckets = set(
                satellite_buckets(
                    [
                        (_status_value(item.processing_status), _cloud(item.cloud_cover))
                        for item in observations.get(parcel.id, [])
                    ]
                )
            )
            missing = self.enterprise._missing_fields(parcel)
            buckets |= business_buckets(
                open_alert=parcel.id in open_parcels,
                missing_fields=missing,
            )
            classified.append((parcel, buckets))

        def count(name: str) -> int:
            return sum(1 for _, buckets in classified if name in buckets)

        farms = self._farms({parcel.farm_id for parcel, _ in classified})
        owners = self._owners({farm.owner_id for farm in farms.values() if farm.owner_id})
        visible = classified
        if bucket:
            visible = [(parcel, buckets) for parcel, buckets in classified if bucket in buckets]
        return EnterpriseDataQuality(
            organization_id=organization_id,
            season_year=season,
            date_from=start,
            date_to=end,
            assigned_parcels=len(parcels),
            usable_scene=count("usable_scene"),
            cloudy_only=count("cloudy_only"),
            no_scene=count("no_scene"),
            insufficient_history=count("insufficient_history"),
            open_alert=count("open_alert"),
            incomplete=count("incomplete"),
            notes=list(SATELLITE_NOTES),
            parcels=[
                EnterpriseDataQualityParcel(
                    parcel_id=parcel.id,
                    parcel_name=parcel.name,
                    farm_id=parcel.farm_id,
                    producer_name=_producer(farms.get(parcel.farm_id), owners),
                    buckets=sorted(buckets),
                )
                for parcel, buckets in visible
            ],
        )

    def _observations(
        self, parcel_ids: set[UUID], start: date, end: date
    ) -> dict[UUID, list[SatelliteObservation]]:
        if not parcel_ids:
            return {}
        rows = self.db.scalars(
            select(SatelliteObservation).where(
                SatelliteObservation.parcel_id.in_(parcel_ids),
                SatelliteObservation.acquisition_date >= start,
                SatelliteObservation.acquisition_date <= end,
            )
        ).all()
        grouped: dict[UUID, list[SatelliteObservation]] = {}
        for item in rows:
            grouped.setdefault(item.parcel_id, []).append(item)
        return grouped

    def _open_alert_parcels(self, parcel_ids: set[UUID]) -> set[UUID]:
        if not parcel_ids:
            return set()
        return set(
            self.db.scalars(
                select(ParcelAlert.parcel_id).where(
                    ParcelAlert.parcel_id.in_(parcel_ids),
                    ParcelAlert.status.in_(_OPEN),
                )
            ).all()
        )

    def _farms(self, farm_ids: set[UUID]) -> dict[UUID, Farm]:
        if not farm_ids:
            return {}
        return {
            item.id: item
            for item in self.db.scalars(select(Farm).where(Farm.id.in_(farm_ids))).all()
        }

    def _owners(self, owner_ids: set[UUID]) -> dict[UUID, User]:
        if not owner_ids:
            return {}
        return {
            item.id: item
            for item in self.db.scalars(select(User).where(User.id.in_(owner_ids))).all()
        }


def _status_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "")


def _cloud(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _producer(farm: Farm | None, owners: dict[UUID, User]) -> str | None:
    if farm is None:
        return None
    public = (farm.public_producer_name or "").strip()
    owner = owners.get(farm.owner_id) if farm.owner_id else None
    owner_name = (owner.full_name or "").strip() if owner else ""
    return public or owner_name or farm.name
