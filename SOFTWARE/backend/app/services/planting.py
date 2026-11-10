from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.enums import OrganicScope, PlantingBatchScope, ProductionMethod, TreeStatus
from app.models.planting import PlantingBatch
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.parcel import ParcelRepository
from app.repositories.row import RowRepository
from app.repositories.tree import TreeRepository
from app.schemas.planting import (
    OrganicRowsUpdate,
    PlantingBatchCreate,
    PlantingBatchRead,
    PlantingDistributionUpdate,
    PlantingSummaryRead,
    PlantingYearBucket,
)
from app.services.planting_resolution import planting_year_distribution


class PlantingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)

    def get_summary(self, parcel_id: UUID, owner_id: UUID) -> PlantingSummaryRead:
        parcel = self._parcel(owner_id, parcel_id)
        rows = self.rows.list_by_parcel(parcel.id)
        trees = [tree for tree, _ in self.trees.list_map_for_parcel(parcel.id)]
        counts, unknown = planting_year_distribution(parcel=parcel, rows=rows, trees=trees)
        active = sum(1 for tree in trees if tree.status == TreeStatus.ACTIVE)
        years = [PlantingYearBucket(year=year, tree_count=count) for year, count in sorted(counts.items())]
        batches = [self.to_batch_read(item) for item in self._list_batches(parcel.id)]

        period_label = self._period_label(years, parcel.default_planting_year)
        precision_note = None
        if unknown > 0:
            precision_note = "Godina sadnje nije precizno definisana za sve biljke."
        elif not years and parcel.default_planting_year is None and not batches:
            precision_note = "Godina sadnje nije precizno definisana za sve biljke."

        return PlantingSummaryRead(
            parcel_id=parcel.id,
            total_active_trees=active,
            default_planting_year=parcel.default_planting_year,
            planting_period_label=period_label,
            years=years,
            unknown_tree_count=unknown,
            precision_note=precision_note,
            batches=batches,
            production_method=parcel.production_method,
            organic_scope=parcel.organic_scope,
        )

    def list_batches(self, parcel_id: UUID, owner_id: UUID) -> list[PlantingBatchRead]:
        parcel = self._parcel(owner_id, parcel_id)
        return [self.to_batch_read(item) for item in self._list_batches(parcel.id)]

    def create_batch(
        self,
        parcel_id: UUID,
        owner_id: UUID,
        payload: PlantingBatchCreate,
        created_by_id: UUID,
    ) -> PlantingBatch:
        parcel = self._parcel(owner_id, parcel_id)
        rows = self.rows.list_by_parcel(parcel.id)
        rows_by_number = {row.row_number: row for row in rows}
        row_id = payload.row_id
        row_from = payload.row_number_from
        row_to = payload.row_number_to

        if payload.scope_type == PlantingBatchScope.ROW:
            if row_id is not None:
                row = next((item for item in rows if item.id == row_id), None)
                if row is None:
                    raise NotFoundError("Red nije pronađen")
                row_from = row.row_number
                row_to = row.row_number
            assert row_from is not None and row_to is not None
            for number in range(row_from, row_to + 1):
                if number not in rows_by_number:
                    raise AppError(f"Red {number} ne postoji na parceli.", status_code=422, code="invalid_row_range")

        batch = PlantingBatch(
            parcel_id=parcel.id,
            year=payload.year,
            quantity=payload.quantity,
            scope_type=payload.scope_type,
            row_id=row_id,
            row_number_from=row_from,
            row_number_to=row_to,
            planted_on=payload.planted_on,
            notes=(payload.notes or "").strip() or None,
            created_by_id=created_by_id,
        )
        self.db.add(batch)

        if payload.apply_to_layout:
            self._apply_batch_years(
                parcel_id=parcel.id,
                year=payload.year,
                quantity=payload.quantity,
                scope_type=payload.scope_type,
                row_from=row_from,
                row_to=row_to,
                rows_by_number=rows_by_number,
                default_planting_year=parcel.default_planting_year,
            )
            if payload.scope_type == PlantingBatchScope.PARCEL and parcel.default_planting_year is None:
                parcel.default_planting_year = payload.year

        self.db.commit()
        self.db.refresh(batch)
        return batch

    def delete_batch(self, parcel_id: UUID, batch_id: UUID, owner_id: UUID) -> None:
        self._parcel(owner_id, parcel_id)
        batch = self.db.get(PlantingBatch, batch_id)
        if batch is None or batch.parcel_id != parcel_id:
            raise NotFoundError("Period sadnje nije pronađen")
        self.db.delete(batch)
        self.db.commit()

    def set_distribution(
        self,
        parcel_id: UUID,
        owner_id: UUID,
        payload: PlantingDistributionUpdate,
        created_by_id: UUID,
    ) -> PlantingSummaryRead:
        """Replace planting years on all active trees to match the given buckets."""
        parcel = self._parcel(owner_id, parcel_id)
        rows = self.rows.list_by_parcel(parcel.id)
        trees = [
            tree
            for tree, _row_number in self.trees.list_map_for_parcel(parcel.id)
            if tree.status == TreeStatus.ACTIVE
        ]
        total = len(trees)
        assigned = sum(item.tree_count for item in payload.years)
        if assigned > total:
            raise AppError(
                f"Zbir stabala ({assigned}) premašuje aktivna stabla ({total}).",
                status_code=422,
                code="planting_distribution_overflow",
            )
        if assigned < total:
            raise AppError(
                f"Zbir stabala ({assigned}) mora biti jednak broju aktivnih stabala ({total}).",
                status_code=422,
                code="planting_distribution_underflow",
            )

        index = 0
        for bucket in sorted(payload.years, key=lambda item: item.year):
            for _ in range(bucket.tree_count):
                trees[index].planting_year = bucket.year
                index += 1

        for row in rows:
            row_trees = [tree for tree in trees if tree.row_id == row.id]
            if not row_trees:
                row.planting_year = None
                continue
            years = {tree.planting_year for tree in row_trees}
            row.planting_year = next(iter(years)) if len(years) == 1 else None

        # Replace declared batches so the editable list stays in sync with layout.
        for batch in self._list_batches(parcel.id):
            self.db.delete(batch)
        for bucket in sorted(payload.years, key=lambda item: item.year):
            self.db.add(
                PlantingBatch(
                    parcel_id=parcel.id,
                    year=bucket.year,
                    quantity=bucket.tree_count,
                    scope_type=PlantingBatchScope.PARCEL,
                    row_number_from=min((row.row_number for row in rows), default=None),
                    row_number_to=max((row.row_number for row in rows), default=None),
                    created_by_id=created_by_id,
                )
            )

        if len(payload.years) == 1:
            parcel.default_planting_year = payload.years[0].year
        elif parcel.default_planting_year is None and payload.years:
            parcel.default_planting_year = min(item.year for item in payload.years)

        self.db.commit()
        return self.get_summary(parcel_id, owner_id)

    def set_organic_rows(self, parcel_id: UUID, owner_id: UUID, payload: OrganicRowsUpdate) -> list[Row]:
        parcel = self._parcel(owner_id, parcel_id)
        if parcel.production_method != ProductionMethod.ORGANIC:
            raise AppError(
                "Parcela mora biti označena kao organska proizvodnja.",
                status_code=422,
                code="not_organic_method",
            )
        if parcel.organic_scope != OrganicScope.PART_OF_PARCEL:
            raise AppError(
                "Organski deo parcele zahteva organic_scope=part_of_parcel.",
                status_code=422,
                code="invalid_organic_scope",
            )
        rows = self.rows.list_by_parcel(parcel.id)
        selected = set(payload.row_ids)
        unknown = selected - {row.id for row in rows}
        if unknown:
            raise NotFoundError("Jedan ili više redova nije pronađeno na parceli")
        for row in rows:
            row.is_organic = row.id in selected
        self.db.commit()
        return rows

    def to_batch_read(self, batch: PlantingBatch) -> PlantingBatchRead:
        return PlantingBatchRead(
            id=batch.id,
            created_at=batch.created_at,
            updated_at=batch.updated_at,
            parcel_id=batch.parcel_id,
            year=batch.year,
            quantity=batch.quantity,
            scope_type=batch.scope_type,
            row_id=batch.row_id,
            row_number_from=batch.row_number_from,
            row_number_to=batch.row_number_to,
            planted_on=batch.planted_on,
            notes=batch.notes,
            created_by_id=batch.created_by_id,
        )

    def _apply_batch_years(
        self,
        *,
        parcel_id: UUID,
        year: int,
        quantity: int,
        scope_type: PlantingBatchScope,
        row_from: int | None,
        row_to: int | None,
        rows_by_number: dict[int, Row],
        default_planting_year: int | None,
    ) -> None:
        """Assign planting year to up to `quantity` active trees in scope.

        Prefers unset trees, then parcel-default year, then other years — so a second
        period fills remaining trees instead of overwriting the first period.
        """
        target_rows: list[Row]
        if scope_type == PlantingBatchScope.PARCEL:
            target_rows = list(rows_by_number.values())
        else:
            assert row_from is not None and row_to is not None
            target_rows = [rows_by_number[number] for number in range(row_from, row_to + 1)]

        target_ids = {row.id for row in target_rows}
        scoped: list[Tree] = []
        for tree, _row_number in self.trees.list_map_for_parcel(parcel_id):
            if tree.row_id not in target_ids:
                continue
            if tree.status != TreeStatus.ACTIVE:
                continue
            scoped.append(tree)

        already = sum(1 for tree in scoped if tree.planting_year == year)
        remaining = max(0, quantity - already)
        if remaining > 0:
            candidates = [tree for tree in scoped if tree.planting_year != year]

            def candidate_priority(tree: Tree) -> int:
                if tree.planting_year is None:
                    return 0
                if default_planting_year is not None and tree.planting_year == default_planting_year:
                    return 1
                return 2

            # Stable sort keeps orchard order within the same priority bucket.
            candidates.sort(key=candidate_priority)
            for tree in candidates[:remaining]:
                tree.planting_year = year

        # Keep row year only when every active tree in the row shares one year.
        for row in target_rows:
            row_trees = [tree for tree in scoped if tree.row_id == row.id]
            if not row_trees:
                continue
            years = {tree.planting_year for tree in row_trees}
            if None in years or len(years) != 1:
                row.planting_year = None
            else:
                row.planting_year = next(iter(years))

    def _list_batches(self, parcel_id: UUID) -> list[PlantingBatch]:
        stmt = (
            select(PlantingBatch)
            .where(PlantingBatch.parcel_id == parcel_id)
            .order_by(PlantingBatch.year, PlantingBatch.created_at)
        )
        return list(self.db.scalars(stmt).all())

    def _period_label(self, years: list[PlantingYearBucket], default_year: int | None) -> str:
        if years:
            values = [item.year for item in years]
            if len(values) == 1:
                return str(values[0])
            return f"{min(values)}–{max(values)}"
        if default_year is not None:
            return str(default_year)
        return "Nepoznato"

    def _parcel(self, owner_id: UUID, parcel_id: UUID):
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel
