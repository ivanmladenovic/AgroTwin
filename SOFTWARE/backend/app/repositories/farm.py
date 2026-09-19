from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.farm import Farm


class FarmRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_owner(self, owner_id: UUID) -> list[Farm]:
        stmt = (
            select(Farm)
            .where(Farm.owner_id == owner_id)
            .options(selectinload(Farm.parcels))
            .order_by(Farm.name)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id_for_owner(self, farm_id: UUID, owner_id: UUID) -> Farm | None:
        stmt = (
            select(Farm)
            .where(Farm.id == farm_id, Farm.owner_id == owner_id)
            .options(selectinload(Farm.parcels))
        )
        return self.db.scalars(stmt).first()

    def add(self, farm: Farm) -> Farm:
        self.db.add(farm)
        return farm
