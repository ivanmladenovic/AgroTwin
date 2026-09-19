from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TreeStatus
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.tree import Tree


class ParcelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_farm(self, farm_id: UUID) -> list[Parcel]:
        stmt = select(Parcel).where(Parcel.farm_id == farm_id).order_by(Parcel.name)
        return list(self.db.scalars(stmt).all())

    def list_for_owner(self, owner_id: UUID) -> list[Parcel]:
        stmt = (
            select(Parcel)
            .join(Farm)
            .where(Farm.owner_id == owner_id)
            .order_by(Parcel.name)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, parcel_id: UUID) -> Parcel | None:
        return self.db.get(Parcel, parcel_id)

    def get_for_owner(self, parcel_id: UUID, owner_id: UUID) -> Parcel | None:
        stmt = (
            select(Parcel)
            .join(Farm)
            .where(Parcel.id == parcel_id, Farm.owner_id == owner_id)
            .options(selectinload(Parcel.farm), selectinload(Parcel.rows))
        )
        return self.db.scalars(stmt).first()

    def tree_count(self, parcel_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Tree)
            .where(Tree.parcel_id == parcel_id, Tree.status == TreeStatus.ACTIVE)
        )
        return int(self.db.scalar(stmt) or 0)

    def total_area_hectares(self, owner_id: UUID, parcel_id: UUID | None = None) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(Parcel.area_hectares), 0))
            .join(Farm)
            .where(Farm.owner_id == owner_id)
        )
        if parcel_id is not None:
            stmt = stmt.where(Parcel.id == parcel_id)
        return Decimal(self.db.scalar(stmt) or 0)

    def add(self, parcel: Parcel) -> Parcel:
        self.db.add(parcel)
        return parcel

    def delete(self, parcel: Parcel) -> None:
        self.db.delete(parcel)
