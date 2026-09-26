from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.soil import SoilProfileSnapshot


class SoilProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_parcel(self, parcel_id: UUID) -> SoilProfileSnapshot | None:
        stmt = select(SoilProfileSnapshot).where(SoilProfileSnapshot.parcel_id == parcel_id)
        return self.db.scalars(stmt).first()

    def add(self, snapshot: SoilProfileSnapshot) -> SoilProfileSnapshot:
        self.db.add(snapshot)
        return snapshot
