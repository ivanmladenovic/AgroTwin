from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import AppError, NotFoundError
from app.core.maps import coordinates_as_decimal, resolve_maps_location
from app.models.enums import HealthStatus, TreeStatus
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.disease import DiseaseRepository
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.row import RowRepository
from app.repositories.tree import TreeRepository
from app.schemas.farm import FarmRead
from app.schemas.journal import TreeOptionRead
from app.schemas.orchard import (
    OrchardStats,
    OrchardTwinRead,
    RowRead,
    TreeDetailRead,
    TreeMapRead,
    WellRead,
)
from app.schemas.parcel import (
    ParcelCreate,
    ParcelRead,
    ParcelUpdate,
    RowPlanItem,
    VarietySpec,
    normalize_varieties_and_plan,
)
from app.services.orchard_layout import format_tree_public_id, generate_rectangular_layout

PARCEL_CODE_MAX_LENGTH = 64


def unique_parcel_code(name: str, existing_codes: set[str], max_length: int = PARCEL_CODE_MAX_LENGTH) -> str:
    base = " ".join(name.split())[:max_length] or "Zasad"
    taken = {item.casefold() for item in existing_codes}
    if base.casefold() not in taken:
        return base
    index = 2
    while True:
        suffix = f" {index}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}" if len(base) + len(suffix) > max_length else f"{base}{suffix}"
        if candidate.casefold() not in taken:
            return candidate
        index += 1


class OrchardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)
        self.diseases = DiseaseRepository(db)

    def list_parcels(self, owner_id: UUID) -> list[ParcelRead]:
        parcels = self.parcels.list_for_owner(owner_id)
        return [self.to_parcel_read(parcel) for parcel in parcels]

    def get_parcel(self, parcel_id: UUID, owner_id: UUID) -> Parcel:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel

    def create_parcel(self, owner_id: UUID, payload: ParcelCreate) -> Parcel:
        farm = self._farm_for_owner(owner_id, payload.farm_id)
        row_varieties = {item.row_number: item.variety for item in payload.row_plan}
        missing = {
            (item.row_number, position)
            for item in payload.row_plan
            for position in item.missing_positions
        }
        try:
            layout = generate_rectangular_layout(
                row_count=payload.row_count,
                trees_per_row=payload.trees_per_row,
                row_spacing_m=payload.row_spacing_m,
                tree_spacing_m=payload.tree_spacing_m,
                starting_tree_number=payload.starting_tree_number,
                default_variety=payload.default_variety,
                planting_year=payload.planting_year,
                well_location=payload.well_location,
                row_varieties=row_varieties,
                missing_positions=missing,
            )
        except ValueError as exc:
            raise AppError(str(exc), status_code=422, code="invalid_orchard") from exc

        parcel = Parcel(
            farm_id=farm.id,
            name=payload.name.strip(),
            code=self._unique_code(farm.id, payload.name.strip()),
            area_hectares=payload.area_hectares,
            notes=payload.notes,
            row_count=payload.row_count,
            trees_per_row=payload.trees_per_row,
            row_spacing_m=payload.row_spacing_m,
            tree_spacing_m=payload.tree_spacing_m,
            default_variety=payload.default_variety,
            varieties=[item.model_dump() for item in payload.varieties],
            default_planting_year=payload.planting_year,
            starting_tree_number=payload.starting_tree_number,
            well_location=payload.well_location,
            well_x=layout.well_x,
            well_y=layout.well_y,
        )
        self._apply_maps_url(parcel, payload.maps_url)
        self.parcels.add(parcel)
        self.db.flush()
        self._persist_layout(parcel, layout)
        self.db.commit()
        self.db.refresh(parcel)
        return parcel

    def update_parcel(self, parcel_id: UUID, owner_id: UUID, payload: ParcelUpdate) -> Parcel:
        parcel = self.get_parcel(parcel_id, owner_id)
        if payload.name is not None:
            parcel.name = payload.name.strip()
            parcel.code = self._unique_code(farm.id, parcel.name, exclude_id=parcel.id)
        if payload.area_hectares is not None:
            parcel.area_hectares = payload.area_hectares
        if payload.notes is not None:
            parcel.notes = payload.notes
        if "maps_url" in payload.model_fields_set:
            self._apply_maps_url(parcel, payload.maps_url)
        if payload.planting_year is not None:
            parcel.default_planting_year = payload.planting_year

        if payload.varieties is not None or payload.row_plan is not None:
            try:
                varieties = (
                    list(payload.varieties)
                    if payload.varieties is not None
                    else [VarietySpec.model_validate(item) for item in (parcel.varieties or [])]
                )
                resolved, default_name, plan = normalize_varieties_and_plan(
                    row_count=parcel.row_count or 0,
                    trees_per_row=parcel.trees_per_row or 0,
                    varieties=varieties,
                    row_plan=payload.row_plan or [],
                    default_variety=parcel.default_variety,
                )
            except (ValueError, ValidationError) as exc:
                raise AppError(str(exc), status_code=422, code="invalid_orchard") from exc
            parcel.varieties = [item.model_dump() for item in resolved]
            parcel.default_variety = default_name
            flag_modified(parcel, "varieties")
            if payload.row_plan is not None:
                self._apply_planting_plan(parcel, plan, planting_year=payload.planting_year or parcel.default_planting_year)

        self.db.commit()
        self.db.refresh(parcel)
        return parcel

    def delete_parcel(self, parcel_id: UUID, owner_id: UUID) -> None:
        parcel = self.get_parcel(parcel_id, owner_id)
        self.db.expire(parcel, ["rows", "trees"])
        self.parcels.delete(parcel)
        self.db.commit()

    def get_twin(self, parcel_id: UUID, owner_id: UUID) -> OrchardTwinRead:
        parcel = self.get_parcel(parcel_id, owner_id)
        row_models = self.rows.list_by_parcel(parcel.id)
        tree_rows = self.trees.list_map_for_parcel(parcel.id)
        health = self.trees.health_counts(parcel.id)
        statuses = self.trees.status_counts(parcel.id)
        severe_ids = self.diseases.severe_tree_ids(parcel.id)
        trees = [
            TreeMapRead(
                id=tree.id,
                created_at=tree.created_at,
                updated_at=tree.updated_at,
                parcel_id=tree.parcel_id,
                row_id=tree.row_id,
                public_id=tree.public_id,
                row_number=row_number,
                position_in_row=tree.position_in_row,
                planting_year=tree.planting_year,
                variety=tree.variety,
                status=tree.status,
                health_status=tree.health_status,
                has_severe_case=tree.id in severe_ids,
                normalized_x=tree.normalized_x,
                normalized_y=tree.normalized_y,
            )
            for tree, row_number in tree_rows
        ]
        active_trees = [tree for tree in trees if tree.status == TreeStatus.ACTIVE]
        width_m = Decimal("0")
        height_m = Decimal("0")
        if parcel.trees_per_row and parcel.tree_spacing_m is not None:
            width_m = Decimal(max(parcel.trees_per_row - 1, 0)) * parcel.tree_spacing_m
        if parcel.row_count and parcel.row_spacing_m is not None:
            height_m = Decimal(max(parcel.row_count - 1, 0)) * parcel.row_spacing_m
        if width_m == 0 and trees:
            width_m = max(tree.normalized_x for tree in trees)
        if height_m == 0 and trees:
            height_m = max(tree.normalized_y for tree in trees)
        well = None
        if parcel.well_location is not None and parcel.well_x is not None and parcel.well_y is not None:
            well = WellRead(location=parcel.well_location, x=parcel.well_x, y=parcel.well_y)
        return OrchardTwinRead(
            parcel=self.to_parcel_read(parcel, tree_count=len(active_trees)),
            farm=FarmRead.model_validate(parcel.farm),
            rows=[RowRead.model_validate(row) for row in row_models],
            trees=trees,
            stats=OrchardStats(
                total_trees=len(active_trees),
                row_count=parcel.row_count or len(row_models),
                trees_per_row=parcel.trees_per_row,
                area_hectares=parcel.area_hectares,
                row_spacing_m=parcel.row_spacing_m,
                tree_spacing_m=parcel.tree_spacing_m,
                healthy_trees=health.get(HealthStatus.HEALTHY, 0),
                monitoring_trees=health.get(HealthStatus.MONITORING, 0),
                issue_trees=health.get(HealthStatus.ISSUE, 0),
                unknown_trees=health.get(HealthStatus.UNKNOWN, 0),
                active_trees=statuses.get(TreeStatus.ACTIVE, 0),
                removed_trees=statuses.get(TreeStatus.REMOVED, 0),
                replaced_trees=statuses.get(TreeStatus.REPLACED, 0),
            ),
            well=well,
            width_m=width_m,
            height_m=height_m,
        )

    def get_tree_detail(self, parcel_id: UUID, tree_id: UUID, owner_id: UUID) -> TreeDetailRead:
        parcel = self.get_parcel(parcel_id, owner_id)
        found = self.trees.get_for_parcel(parcel.id, tree_id)
        if found is None:
            raise NotFoundError("Stablo nije pronađeno")
        tree, row_number = found
        return TreeDetailRead(
            id=tree.id,
            created_at=tree.created_at,
            updated_at=tree.updated_at,
            parcel_id=tree.parcel_id,
            row_id=tree.row_id,
            public_id=tree.public_id,
            row_number=row_number,
            position_in_row=tree.position_in_row,
            planting_year=tree.planting_year,
            variety=tree.variety,
            status=tree.status,
            health_status=tree.health_status,
            has_severe_case=tree.id in self.diseases.severe_tree_ids(parcel.id),
            normalized_x=tree.normalized_x,
            normalized_y=tree.normalized_y,
            activity_count=self.trees.activity_count(tree.id),
            disease_issue_count=self.trees.open_disease_count(tree.id),
            total_cost=self.trees.total_cost(tree.id),
            journal_path=f"/orchard/{parcel.id}/trees/{tree.id}",
        )

    def list_rows(self, parcel_id: UUID, owner_id: UUID) -> list[RowRead]:
        parcel = self.get_parcel(parcel_id, owner_id)
        return [RowRead.model_validate(row) for row in self.rows.list_by_parcel(parcel.id)]

    def list_tree_options(
        self, parcel_id: UUID, owner_id: UUID, row_id: UUID | None = None
    ) -> list[TreeOptionRead]:
        parcel = self.get_parcel(parcel_id, owner_id)
        return [
            TreeOptionRead(
                id=tree.id,
                public_id=tree.public_id,
                row_id=tree.row_id,
                row_number=row_number,
                position_in_row=tree.position_in_row,
                variety=tree.variety,
            )
            for tree, row_number in self.trees.list_options(parcel.id, row_id)
            if tree.status == TreeStatus.ACTIVE
        ]

    def _apply_planting_plan(
        self,
        parcel: Parcel,
        plan: list[RowPlanItem],
        planting_year: int | None,
    ) -> None:
        rows = {row.row_number: row for row in self.rows.list_by_parcel(parcel.id)}
        existing: dict[tuple[int, int], Tree] = {}
        for tree, row_number in self.trees.list_map_for_parcel(parcel.id):
            existing[(row_number, tree.position_in_row)] = tree
        used_ids = {tree.public_id for tree in existing.values()}
        trees_per_row = parcel.trees_per_row or 0
        row_spacing = parcel.row_spacing_m or Decimal("5")
        tree_spacing = parcel.tree_spacing_m or Decimal("3.5")
        starting = parcel.starting_tree_number or 1
        inserts: list[dict[str, object]] = []

        for item in plan:
            row = rows.get(item.row_number)
            if row is None:
                continue
            row.variety = item.variety
            missing = set(item.missing_positions)
            active = 0
            for position in range(1, trees_per_row + 1):
                tree = existing.get((item.row_number, position))
                if position in missing:
                    if tree is not None:
                        self._remove_or_delete_tree(tree)
                    continue
                active += 1
                if tree is not None:
                    tree.status = TreeStatus.ACTIVE
                    tree.variety = item.variety
                    continue
                sequence = starting + (item.row_number - 1) * trees_per_row + (position - 1)
                public_id = format_tree_public_id(item.row_number, sequence)
                if public_id in used_ids:
                    public_id = f"{public_id}-R"
                used_ids.add(public_id)
                inserts.append(
                    {
                        "id": uuid4(),
                        "parcel_id": parcel.id,
                        "row_id": row.id,
                        "public_id": public_id,
                        "position_in_row": position,
                        "planting_year": planting_year,
                        "variety": item.variety,
                        "status": TreeStatus.ACTIVE.value,
                        "health_status": HealthStatus.HEALTHY.value,
                        "normalized_x": Decimal(position - 1) * tree_spacing,
                        "normalized_y": Decimal(item.row_number - 1) * row_spacing,
                    }
                )
            row.tree_count = active
        self.trees.bulk_insert(inserts)
        self.db.flush()

    def _remove_or_delete_tree(self, tree: Tree) -> None:
        if self.trees.has_records(tree.id):
            tree.status = TreeStatus.REMOVED
            return
        self.trees.delete(tree)

    def _persist_layout(self, parcel: Parcel, layout: object) -> None:
        from app.services.orchard_layout import OrchardLayout

        assert isinstance(layout, OrchardLayout)
        generated_rows: list[tuple[object, Row]] = []
        for layout_row in layout.rows:
            row = Row(
                id=uuid4(),
                parcel_id=parcel.id,
                row_number=layout_row.row_number,
                tree_count=layout_row.tree_count,
                name=f"Red {layout_row.row_number:02d}",
                variety=layout_row.variety,
            )
            self.rows.add(row)
            generated_rows.append((layout_row, row))
        self.db.flush()
        tree_rows: list[dict[str, object]] = []
        for layout_row, row in generated_rows:
            for tree in layout_row.trees:  # type: ignore[attr-defined]
                tree_rows.append(
                    {
                        "id": uuid4(),
                        "parcel_id": parcel.id,
                        "row_id": row.id,
                        "public_id": tree.public_id,
                        "position_in_row": tree.position_in_row,
                        "planting_year": tree.planting_year,
                        "variety": tree.variety,
                        "status": TreeStatus.ACTIVE.value,
                        "health_status": HealthStatus.HEALTHY.value,
                        "normalized_x": tree.normalized_x,
                        "normalized_y": tree.normalized_y,
                    }
                )
        self.trees.bulk_insert(tree_rows)

    def _apply_maps_url(self, parcel: Parcel, maps_url: str | None) -> None:
        parcel.maps_url = maps_url
        if not maps_url:
            parcel.latitude = None
            parcel.longitude = None
            return
        try:
            location = resolve_maps_location(maps_url, fallback_query=parcel.name)
        except Exception:
            return
        if location is None:
            return
        parcel.latitude, parcel.longitude = coordinates_as_decimal(location)

    def to_parcel_read(self, parcel: Parcel, tree_count: int | None = None) -> ParcelRead:
        data = ParcelRead.model_validate(parcel)
        return data.model_copy(
            update={"tree_count": tree_count if tree_count is not None else self.parcels.tree_count(parcel.id)}
        )

    def _unique_code(self, farm_id: UUID, name: str, exclude_id: UUID | None = None) -> str:
        return unique_parcel_code(
            name,
            {
                parcel.code
                for parcel in self.parcels.list_by_farm(farm_id)
                if exclude_id is None or parcel.id != exclude_id
            },
        )

    def _farm_for_owner(self, owner_id: UUID, farm_id: UUID | None) -> Farm:
        if farm_id is not None:
            farm = self.farms.get_by_id_for_owner(farm_id, owner_id)
            if farm is None:
                raise NotFoundError("Gazdinstvo nije pronađeno")
            return farm
        farms = self.farms.list_by_owner(owner_id)
        if farms:
            return farms[0]
        farm = Farm(owner_id=owner_id, name="Moj voćnjak")
        self.farms.add(farm)
        self.db.flush()
        return farm
