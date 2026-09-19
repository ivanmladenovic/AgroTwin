from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.cost import Cost
from app.models.disease import DiseaseCase
from app.models.enums import DiseaseCaseStatus, HealthStatus, TreeStatus
from app.models.row import Row
from app.models.tree import Tree


class TreeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_map_for_parcel(self, parcel_id: UUID) -> list[tuple[Tree, int]]:
        stmt = (
            select(Tree, Row.row_number)
            .join(Row, Tree.row_id == Row.id)
            .where(Tree.parcel_id == parcel_id)
            .order_by(Row.row_number, Tree.position_in_row)
        )
        return list(self.db.execute(stmt).all())

    def get_for_parcel(self, parcel_id: UUID, tree_id: UUID) -> tuple[Tree, int] | None:
        stmt = (
            select(Tree, Row.row_number)
            .join(Row, Tree.row_id == Row.id)
            .where(Tree.parcel_id == parcel_id, Tree.id == tree_id)
        )
        return self.db.execute(stmt).first()

    def list_options(self, parcel_id: UUID, row_id: UUID | None = None) -> list[tuple[Tree, int]]:
        stmt = (
            select(Tree, Row.row_number)
            .join(Row, Tree.row_id == Row.id)
            .where(Tree.parcel_id == parcel_id)
            .order_by(Row.row_number, Tree.position_in_row)
        )
        if row_id is not None:
            stmt = stmt.where(Tree.row_id == row_id)
        return list(self.db.execute(stmt).all())

    def active_count(self, owner_id: UUID, parcel_id: UUID | None = None) -> int:
        from app.models.farm import Farm
        from app.models.parcel import Parcel

        stmt = (
            select(func.count())
            .select_from(Tree)
            .join(Parcel, Tree.parcel_id == Parcel.id)
            .join(Farm, Parcel.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id, Tree.status == TreeStatus.ACTIVE)
        )
        if parcel_id is not None:
            stmt = stmt.where(Tree.parcel_id == parcel_id)
        return int(self.db.scalar(stmt) or 0)

    def health_counts(self, parcel_id: UUID) -> dict[HealthStatus, int]:
        stmt = (
            select(Tree.health_status, func.count())
            .where(Tree.parcel_id == parcel_id)
            .group_by(Tree.health_status)
        )
        return {status: count for status, count in self.db.execute(stmt).all()}

    def status_counts(self, parcel_id: UUID) -> dict[TreeStatus, int]:
        stmt = (
            select(Tree.status, func.count())
            .where(Tree.parcel_id == parcel_id)
            .group_by(Tree.status)
        )
        return {status: count for status, count in self.db.execute(stmt).all()}

    def activity_count(self, tree_id: UUID) -> int:
        stmt = select(func.count()).select_from(Activity).where(Activity.tree_id == tree_id)
        return int(self.db.scalar(stmt) or 0)

    def open_disease_count(self, tree_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(DiseaseCase)
            .where(
                DiseaseCase.tree_id == tree_id,
                DiseaseCase.status != DiseaseCaseStatus.RESOLVED,
            )
        )
        return int(self.db.scalar(stmt) or 0)

    def total_cost(self, tree_id: UUID) -> Decimal:
        stmt = select(func.coalesce(func.sum(Cost.amount), 0)).where(Cost.tree_id == tree_id)
        return Decimal(self.db.scalar(stmt) or 0)

    def bulk_insert(self, rows: Sequence[dict[str, object]]) -> None:
        if not rows:
            return
        self.db.execute(insert(Tree), list(rows))

    def disease_count(self, tree_id: UUID) -> int:
        stmt = select(func.count()).select_from(DiseaseCase).where(DiseaseCase.tree_id == tree_id)
        return int(self.db.scalar(stmt) or 0)

    def has_records(self, tree_id: UUID) -> bool:
        return self.activity_count(tree_id) > 0 or self.disease_count(tree_id) > 0 or self.total_cost(tree_id) > 0

    def delete(self, tree: Tree) -> None:
        self.db.delete(tree)
