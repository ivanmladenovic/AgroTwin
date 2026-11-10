from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import SatelliteProcessingStatus
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.satellite import SatelliteAnomaly, SatelliteObservation, SatelliteZoneMetric


class SatelliteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_observation(self, observation_id: UUID) -> SatelliteObservation | None:
        return self.db.scalars(
            select(SatelliteObservation)
            .where(SatelliteObservation.id == observation_id)
            .options(
                selectinload(SatelliteObservation.zones),
                selectinload(SatelliteObservation.anomalies),
            )
        ).first()

    def get_by_product(
        self,
        parcel_id: UUID,
        provider: str,
        product_id: str,
    ) -> SatelliteObservation | None:
        return self.db.scalars(
            select(SatelliteObservation).where(
                SatelliteObservation.parcel_id == parcel_id,
                SatelliteObservation.provider == provider,
                SatelliteObservation.product_id == product_id,
            )
        ).first()

    def list_for_parcel(
        self,
        parcel_id: UUID,
        *,
        limit: int = 50,
        completed_only: bool = False,
    ) -> list[SatelliteObservation]:
        stmt = (
            select(SatelliteObservation)
            .where(SatelliteObservation.parcel_id == parcel_id)
            .order_by(SatelliteObservation.acquisition_date.desc(), SatelliteObservation.created_at.desc())
            .limit(limit)
            .options(
                selectinload(SatelliteObservation.zones),
                selectinload(SatelliteObservation.anomalies),
            )
        )
        if completed_only:
            stmt = stmt.where(
                SatelliteObservation.processing_status == SatelliteProcessingStatus.COMPLETED
            )
        return list(self.db.scalars(stmt).all())

    def latest_completed(self, parcel_id: UUID) -> SatelliteObservation | None:
        items = self.list_for_parcel(parcel_id, limit=1, completed_only=True)
        return items[0] if items else None

    def previous_completed(
        self,
        parcel_id: UUID,
        before: SatelliteObservation,
        *,
        offset: int = 1,
    ) -> SatelliteObservation | None:
        items = self.list_for_parcel(parcel_id, limit=offset + 1, completed_only=True)
        if len(items) <= offset:
            return None
        # items[0] is latest; find `before` then return next
        for index, item in enumerate(items):
            if item.id == before.id and index + offset < len(items):
                return items[index + offset]
        if items and items[0].id != before.id and len(items) > offset:
            return items[offset]
        return None

    def list_parcels_with_boundary(self) -> list[Parcel]:
        stmt = select(Parcel).where(Parcel.boundary.is_not(None)).order_by(Parcel.name)
        return list(self.db.scalars(stmt).all())

    def list_parcels_for_owner(self, owner_id: UUID) -> list[Parcel]:
        stmt = (
            select(Parcel)
            .join(Farm)
            .where(Farm.owner_id == owner_id, Parcel.boundary.is_not(None))
            .order_by(Parcel.name)
        )
        return list(self.db.scalars(stmt).all())

    def add_observation(self, observation: SatelliteObservation) -> SatelliteObservation:
        self.db.add(observation)
        return observation

    def add_zone(self, zone: SatelliteZoneMetric) -> SatelliteZoneMetric:
        self.db.add(zone)
        return zone

    def add_anomaly(self, anomaly: SatelliteAnomaly) -> SatelliteAnomaly:
        self.db.add(anomaly)
        return anomaly

    def get_for_owner(self, observation_id: UUID, owner_id: UUID) -> SatelliteObservation | None:
        stmt = (
            select(SatelliteObservation)
            .join(Parcel, SatelliteObservation.parcel_id == Parcel.id)
            .join(Farm, Parcel.farm_id == Farm.id)
            .where(SatelliteObservation.id == observation_id, Farm.owner_id == owner_id)
            .options(
                selectinload(SatelliteObservation.zones),
                selectinload(SatelliteObservation.anomalies),
            )
        )
        return self.db.scalars(stmt).first()
