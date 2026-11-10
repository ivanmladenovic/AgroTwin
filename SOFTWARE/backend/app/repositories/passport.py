from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.farm import Farm
from app.models.passport import HarvestLot, HarvestLotSequence, PassportSnapshot


class PassportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[HarvestLot]]:
        return (
            select(HarvestLot)
            .join(Farm, HarvestLot.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(
                selectinload(HarvestLot.farm).selectinload(Farm.owner),
                selectinload(HarvestLot.parcel),
                selectinload(HarvestLot.snapshots),
            )
        )

    def get_for_owner(self, lot_id: UUID, owner_id: UUID) -> HarvestLot | None:
        stmt = self._owned(owner_id).where(HarvestLot.id == lot_id)
        return self.db.scalars(stmt).unique().first()

    def get_by_harvest_for_owner(self, harvest_id: UUID, owner_id: UUID) -> HarvestLot | None:
        stmt = self._owned(owner_id).where(HarvestLot.harvest_id == harvest_id)
        return self.db.scalars(stmt).unique().first()

    def list_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        harvest_id: UUID | None = None,
    ) -> list[HarvestLot]:
        stmt = self._owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(HarvestLot.parcel_id == parcel_id)
        if harvest_id is not None:
            stmt = stmt.where(HarvestLot.harvest_id == harvest_id)
        stmt = stmt.order_by(HarvestLot.harvest_date.desc(), HarvestLot.created_at.desc())
        return list(self.db.scalars(stmt).unique().all())

    def get_by_token(self, token: str) -> HarvestLot | None:
        stmt = (
            select(HarvestLot)
            .where(HarvestLot.passport_token == token)
            .options(
                selectinload(HarvestLot.farm).selectinload(Farm.owner),
                selectinload(HarvestLot.parcel),
                selectinload(HarvestLot.snapshots),
            )
        )
        return self.db.scalars(stmt).unique().first()

    def add(self, lot: HarvestLot) -> HarvestLot:
        self.db.add(lot)
        return lot

    def add_snapshot(self, snapshot: PassportSnapshot) -> PassportSnapshot:
        self.db.add(snapshot)
        return snapshot

    def next_lot_number(self, year: int) -> str:
        """Allocate AT-YYYY-NNNNN under a row lock."""
        stmt = (
            select(HarvestLotSequence)
            .where(HarvestLotSequence.year == year)
            .with_for_update()
        )
        seq = self.db.scalars(stmt).first()
        if seq is None:
            seq = HarvestLotSequence(year=year, last_value=0)
            self.db.add(seq)
            self.db.flush()
        seq.last_value += 1
        self.db.flush()
        return f"AT-{year}-{seq.last_value:05d}"
