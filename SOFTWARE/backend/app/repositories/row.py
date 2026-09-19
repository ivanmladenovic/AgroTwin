from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.row import Row


class RowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_parcel(self, parcel_id: UUID) -> list[Row]:
        stmt = select(Row).where(Row.parcel_id == parcel_id).order_by(Row.row_number)
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, row_id: UUID) -> Row | None:
        return self.db.get(Row, row_id)

    def get_for_parcel(self, parcel_id: UUID, row_id: UUID) -> Row | None:
        stmt = select(Row).where(Row.parcel_id == parcel_id, Row.id == row_id)
        return self.db.scalars(stmt).first()

    def add(self, row: Row) -> Row:
        self.db.add(row)
        return row
