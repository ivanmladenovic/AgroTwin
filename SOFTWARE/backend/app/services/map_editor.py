"""Parcel map editor service — additive geographic layout; does not touch schematic canvas flows."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import AppError, NotFoundError
from app.map_editor.layout import generate_planting_layout
from app.map_editor.metrics import polygon_metrics
from app.map_editor.validation import MapEditorGeometryError, validate_editor_boundary
from app.models.enums import HealthStatus, TreeStatus
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.row import RowRepository
from app.repositories.tree import TreeRepository
from app.schemas.map_editor import (
    MapEditorCommitRequest,
    MapEditorCommitResult,
    MapEditorDraftCreate,
    MapEditorExistingRowRead,
    MapEditorExistingTreeRead,
    MapEditorMetricsRead,
    MapEditorPlantingConfig,
    MapEditorPreviewRead,
    MapEditorPreviewRequest,
    MapEditorStateRead,
)
from app.services.orchard import OrchardService, unique_parcel_code
from app.services.orchard_layout import format_tree_public_id


def local_xy_from_latlng(
    lat: float,
    lng: float,
    origin_lat: float,
    origin_lng: float,
) -> tuple[Decimal, Decimal]:
    """Meters east / south of NW origin — matches OrchardCanvas (y grows downward)."""
    m_lat = 111_320.0
    m_lon = 111_320.0 * math.cos(math.radians(origin_lat))
    x = (lng - origin_lng) * m_lon
    y = (origin_lat - lat) * m_lat
    return Decimal(str(round(x, 4))), Decimal(str(round(y, 4)))


def geo_origin_from_points(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """NW corner of a lat/lng cloud."""
    if not points:
        return None
    return max(p[0] for p in points), min(p[1] for p in points)


class MapEditorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orchard = OrchardService(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)
        self.farms = FarmRepository(db)

    def get_state(self, owner_id: UUID, parcel_id: UUID) -> MapEditorStateRead:
        parcel = self.orchard.get_parcel(parcel_id, owner_id)
        rows = sorted(parcel.rows, key=lambda r: r.row_number)
        trees = list(parcel.trees)
        row_number_by_id = {row.id: row.row_number for row in rows}
        warnings: list[str] = []
        metrics = None
        suggested = None
        if parcel.boundary:
            try:
                metrics_raw = polygon_metrics(parcel.boundary)
                metrics = MapEditorMetricsRead.model_validate(metrics_raw)
                if metrics_raw.get("self_intersecting"):
                    warnings.append("Sačuvana granica se seče sama sa sobom.")
            except Exception:
                warnings.append("Sačuvana granica nije validna za metričke proračune.")
        else:
            warnings.append(
                "Parcela nema geografsku granicu. Nacrtajte poligon ili uvežite koordinate — "
                "postojeći pravougaoni šematski raspored ostaje netaknut."
            )

        geo_trees = sum(1 for t in trees if t.latitude is not None and t.longitude is not None)
        schematic_only = bool(trees) and geo_trees == 0
        if schematic_only:
            warnings.append(
                "Stabla imaju samo šematski raspored (normalized_x/y), bez lat/lng. "
                "Generisanje novog rasporeda neće ih obrisati dok eksplicitno ne potvrdite zamenu."
            )

        return MapEditorStateRead(
            parcel_id=parcel.id,
            name=parcel.name,
            farm_id=parcel.farm_id,
            boundary=parcel.boundary,
            latitude=parcel.latitude,
            longitude=parcel.longitude,
            area_hectares=parcel.area_hectares,
            row_spacing_m=parcel.row_spacing_m,
            tree_spacing_m=parcel.tree_spacing_m,
            default_variety=parcel.default_variety,
            varieties=list(parcel.varieties or []),
            default_planting_year=parcel.default_planting_year,
            map_layout=parcel.map_layout,
            metrics=metrics,
            has_geographic_boundary=parcel.boundary is not None,
            has_schematic_only_layout=schematic_only,
            rows=[
                MapEditorExistingRowRead(
                    id=row.id,
                    row_number=row.row_number,
                    tree_count=row.tree_count,
                    variety=row.variety,
                    planting_year=row.planting_year,
                    geometry=row.geometry,
                    segment_count=row.segment_count or 1,
                )
                for row in rows
            ],
            trees=[
                MapEditorExistingTreeRead(
                    id=tree.id,
                    public_id=tree.public_id,
                    row_id=tree.row_id,
                    row_number=row_number_by_id.get(tree.row_id, 0),
                    position_in_row=tree.position_in_row,
                    latitude=float(tree.latitude) if tree.latitude is not None else None,
                    longitude=float(tree.longitude) if tree.longitude is not None else None,
                    variety=tree.variety,
                    planting_year=tree.planting_year,
                    status=tree.status.value if hasattr(tree.status, "value") else str(tree.status),
                    has_geographic_position=tree.latitude is not None and tree.longitude is not None,
                )
                for tree in trees
            ],
            suggested_orientation_deg=suggested,
            warnings=warnings,
        )

    def compute_metrics(self, owner_id: UUID, parcel_id: UUID | None, boundary: dict) -> MapEditorMetricsRead:
        if parcel_id is not None:
            self.orchard.get_parcel(parcel_id, owner_id)
        try:
            geometry = validate_editor_boundary(boundary)
        except MapEditorGeometryError as exc:
            raise AppError(str(exc), code=exc.code, status_code=400) from exc
        return MapEditorMetricsRead.model_validate(polygon_metrics(geometry))

    def preview(self, owner_id: UUID, parcel_id: UUID | None, payload: MapEditorPreviewRequest) -> MapEditorPreviewRead:
        if parcel_id is not None:
            self.orchard.get_parcel(parcel_id, owner_id)
        try:
            raw = generate_planting_layout(
                payload.boundary,
                orientation_deg=payload.config.orientation_deg,
                orientation_edge_index=payload.config.orientation_edge_index,
                row_spacing_m=payload.config.row_spacing_m,
                tree_spacing_m=payload.config.tree_spacing_m,
                first_row_offset_m=payload.config.first_row_offset_m,
                last_row_offset_m=payload.config.last_row_offset_m,
                row_end_offset_m=payload.config.row_end_offset_m,
                tree_start_offset_m=payload.config.tree_start_offset_m,
                boundary_buffer_m=payload.config.boundary_buffer_m,
                target_row_count=payload.config.target_row_count,
                start_row_number=payload.config.start_row_number,
                number_rows_ascending=payload.config.number_rows_ascending,
                default_variety=payload.config.default_variety,
                default_planting_year=payload.config.default_planting_year,
            )
        except MapEditorGeometryError as exc:
            raise AppError(str(exc), code=exc.code, status_code=400) from exc
        return MapEditorPreviewRead.model_validate(raw)

    def commit(self, owner_id: UUID, parcel_id: UUID, payload: MapEditorCommitRequest) -> MapEditorCommitResult:
        parcel = self.orchard.get_parcel(parcel_id, owner_id)
        try:
            geometry = validate_editor_boundary(payload.boundary)
        except MapEditorGeometryError as exc:
            raise AppError(str(exc), code=exc.code, status_code=400) from exc

        metrics_raw = polygon_metrics(geometry)
        metrics = MapEditorMetricsRead.model_validate(metrics_raw)

        # Always persist boundary (additive — existing schematic layout untouched unless replace)
        parcel.boundary = geometry
        flag_modified(parcel, "boundary")

        if payload.update_area_from_geometry:
            parcel.area_hectares = Decimal(str(round(metrics.area_ha, 4)))

        # Centroid for weather / maps convenience
        if metrics.origin_lat is not None and metrics.origin_lon is not None:
            parcel.latitude = Decimal(str(round(metrics.origin_lat, 6)))
            parcel.longitude = Decimal(str(round(metrics.origin_lon, 6)))

        parcel.row_spacing_m = Decimal(str(payload.config.row_spacing_m))
        parcel.tree_spacing_m = Decimal(str(payload.config.tree_spacing_m))
        if payload.config.default_variety:
            parcel.default_variety = payload.config.default_variety
        if payload.config.default_planting_year:
            parcel.default_planting_year = payload.config.default_planting_year
        if payload.varieties is not None:
            parcel.varieties = [v.model_dump() for v in payload.varieties]
            flag_modified(parcel, "varieties")
            if payload.varieties and not parcel.default_variety:
                parcel.default_variety = payload.varieties[0].name

        preview_rows = payload.rows
        preview_trees = payload.trees
        if preview_rows is None or preview_trees is None:
            preview = self.preview(
                owner_id,
                parcel_id,
                MapEditorPreviewRequest(boundary=geometry, config=payload.config),
            )
            preview_rows = preview.rows
            preview_trees = preview.trees

        map_layout = {
            "version": 1,
            "source": "map_editor",
            "config": payload.config.model_dump(),
            "metrics": metrics.model_dump(),
            "committed_at": datetime.now(timezone.utc).isoformat(),
            "replace_planting": payload.replace_planting,
            "summary": {
                "row_count": len({r.row_number for r in preview_rows}),
                "segment_count": len(preview_rows),
                "tree_count": len(preview_trees),
            },
        }
        parcel.map_layout = map_layout
        flag_modified(parcel, "map_layout")

        rows_updated = 0
        trees_updated = 0
        trees_created = 0
        trees_removed = 0
        warnings: list[str] = []

        # Merge segment geometries per logical row_number
        by_row: dict[int, list] = {}
        for draft in preview_rows:
            by_row.setdefault(draft.row_number, []).append(draft)

        existing_rows = {row.row_number: row for row in parcel.rows}

        for row_number, drafts in sorted(by_row.items()):
            geom = _merge_row_geometries(drafts)
            variety = drafts[0].default_variety
            planting_year = drafts[0].default_planting_year
            tree_count = sum(d.tree_count for d in drafts)
            row = existing_rows.get(row_number)
            if row is None:
                if not payload.replace_planting and not payload.create_missing_trees:
                    continue
                row = Row(
                    parcel_id=parcel.id,
                    row_number=row_number,
                    tree_count=tree_count,
                    variety=variety,
                    planting_year=planting_year,
                    geometry=geom,
                    segment_count=len(drafts),
                )
                self.db.add(row)
                self.db.flush()
                existing_rows[row_number] = row
            else:
                row.geometry = geom
                row.segment_count = len(drafts)
                if variety:
                    row.variety = variety
                if planting_year:
                    row.planting_year = planting_year
                if payload.replace_planting:
                    row.tree_count = tree_count
            rows_updated += 1

        if payload.replace_planting:
            trees_updated, trees_created, trees_removed, plant_warnings = self._apply_planting(
                parcel,
                existing_rows,
                preview_trees,
                create_missing=payload.create_missing_trees,
                remove_unmatched=payload.remove_unmatched_trees,
                config=payload.config,
            )
            warnings.extend(plant_warnings)
            parcel.row_count = len(by_row)
            per_row_counts = [
                sum(1 for t in preview_trees if t.row_number == row_number)
                for row_number in by_row
            ]
            parcel.trees_per_row = max(per_row_counts) if per_row_counts else 0
        else:
            warnings.append(
                "Granica i konfiguracija su sačuvani. Geografske pozicije stabala nisu menjane "
                "(uključite zamenu sadnje da primenite raspored)."
            )

        self.db.commit()
        self.db.refresh(parcel)

        return MapEditorCommitResult(
            parcel_id=parcel.id,
            boundary=geometry,
            metrics=metrics,
            map_layout=map_layout,
            rows_updated=rows_updated,
            trees_updated=trees_updated,
            trees_created=trees_created,
            trees_removed=trees_removed,
            warnings=warnings,
            committed_at=datetime.now(timezone.utc),
        )

    def create_draft_parcel(self, owner_id: UUID, payload: MapEditorDraftCreate) -> MapEditorStateRead:
        try:
            geometry = validate_editor_boundary(payload.boundary)
        except MapEditorGeometryError as exc:
            raise AppError(str(exc), code=exc.code, status_code=400) from exc

        farm = self.orchard._farm_for_owner(owner_id, payload.farm_id)
        metrics = polygon_metrics(geometry)
        code = unique_parcel_code(
            payload.name,
            {p.code for p in self.parcels.list_by_farm(farm.id)},
        )
        config = payload.config or MapEditorPlantingConfig(
            orientation_deg=0,
            row_spacing_m=4.5,
            tree_spacing_m=3.5,
        )
        parcel = Parcel(
            farm_id=farm.id,
            name=payload.name.strip(),
            code=code,
            area_hectares=Decimal(str(round(metrics["area_ha"], 4))),
            latitude=Decimal(str(round(metrics["origin_lat"], 6))) if metrics.get("origin_lat") else None,
            longitude=Decimal(str(round(metrics["origin_lon"], 6))) if metrics.get("origin_lon") else None,
            boundary=geometry,
            row_spacing_m=Decimal(str(config.row_spacing_m)),
            tree_spacing_m=Decimal(str(config.tree_spacing_m)),
            default_variety=config.default_variety,
            default_planting_year=config.default_planting_year,
            varieties=[],
            row_count=0,
            trees_per_row=0,
            map_layout={
                "version": 1,
                "source": "map_editor",
                "config": config.model_dump(),
                "draft": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.parcels.add(parcel)
        self.db.flush()

        if payload.commit_planting:
            self.commit(
                owner_id,
                parcel.id,
                MapEditorCommitRequest(
                    boundary=geometry,
                    config=config,
                    replace_planting=True,
                    create_missing_trees=True,
                    remove_unmatched_trees=False,
                ),
            )
        else:
            self.db.commit()

        return self.get_state(owner_id, parcel.id)

    def _apply_planting(
        self,
        parcel: Parcel,
        rows_by_number: dict[int, Row],
        draft_trees: list,
        *,
        create_missing: bool,
        remove_unmatched: bool,
        config: MapEditorPlantingConfig,
    ) -> tuple[int, int, int, list[str]]:
        warnings: list[str] = []
        updated = 0
        created = 0
        removed = 0

        origin = geo_origin_from_points([(float(d.latitude), float(d.longitude)) for d in draft_trees])
        if origin is None:
            warnings.append("Nema sadnica sa koordinatama — šematski raspored nije ažuriran.")
            return 0, 0, 0, warnings
        origin_lat, origin_lng = origin

        row_number_by_id = {row.id: row.row_number for row in rows_by_number.values()}
        # Index existing trees by (row_number, position_in_row)
        existing_index: dict[tuple[int, int], Tree] = {}
        for tree in list(parcel.trees):
            row_num = row_number_by_id.get(tree.row_id)
            if row_num is None:
                continue
            existing_index[(row_num, tree.position_in_row)] = tree

        matched_ids: set[UUID] = set()
        for draft in draft_trees:
            key = (draft.row_number, draft.tree_number)
            row = rows_by_number.get(draft.row_number)
            if row is None:
                continue
            nx, ny = local_xy_from_latlng(
                float(draft.latitude),
                float(draft.longitude),
                origin_lat,
                origin_lng,
            )
            tree = existing_index.get(key)
            if tree is not None:
                tree.latitude = Decimal(str(round(draft.latitude, 6)))
                tree.longitude = Decimal(str(round(draft.longitude, 6)))
                tree.normalized_x = nx
                tree.normalized_y = ny
                if draft.variety is not None:
                    tree.variety = draft.variety
                elif config.default_variety and tree.variety is None:
                    tree.variety = config.default_variety
                if draft.planting_year is not None:
                    tree.planting_year = draft.planting_year
                matched_ids.add(tree.id)
                updated += 1
            elif create_missing:
                public_id = format_tree_public_id(draft.row_number, draft.tree_number)
                tree = Tree(
                    parcel_id=parcel.id,
                    row_id=row.id,
                    public_id=public_id,
                    position_in_row=draft.tree_number,
                    planting_year=draft.planting_year or config.default_planting_year,
                    variety=draft.variety or config.default_variety or row.variety,
                    status=TreeStatus.ACTIVE,
                    health_status=HealthStatus.HEALTHY,
                    normalized_x=nx,
                    normalized_y=ny,
                    latitude=Decimal(str(round(draft.latitude, 6))),
                    longitude=Decimal(str(round(draft.longitude, 6))),
                )
                self.db.add(tree)
                created += 1

        self.db.flush()
        # Re-index matched ids after flush for newly created trees
        for tree in list(parcel.trees):
            row_num = row_number_by_id.get(tree.row_id)
            if row_num is None:
                continue
            if (row_num, tree.position_in_row) in {(d.row_number, d.tree_number) for d in draft_trees}:
                matched_ids.add(tree.id)

        if remove_unmatched:
            for tree in list(parcel.trees):
                if tree.id not in matched_ids and tree.id is not None:
                    # Soft approach: mark removed rather than hard-delete journal history
                    if tree.status != TreeStatus.REMOVED:
                        tree.status = TreeStatus.REMOVED
                        removed += 1
            if removed:
                warnings.append(
                    f"{removed} postojećih stabala označeno kao uklonjeno jer nisu odgovarala novom rasporedu."
                )
        else:
            unmatched = sum(1 for t in parcel.trees if t.id not in matched_ids)
            if unmatched and create_missing:
                warnings.append(
                    f"{unmatched} postojećih stabala nije poklopljeno sa novim rasporedom — ostavljena netaknuta."
                )

        # Refresh row tree_count for active trees
        for row in rows_by_number.values():
            row.tree_count = sum(
                1 for d in draft_trees if d.row_number == row.row_number
            )

        return updated, created, removed, warnings

    def repair_normalized_from_geo(self, parcel: Parcel) -> int:
        """Backfill schematic coords from lat/lng (e.g. parcels saved before this fix)."""
        geo_trees = [
            t
            for t in parcel.trees
            if t.latitude is not None and t.longitude is not None and t.status != TreeStatus.REMOVED
        ]
        if not geo_trees:
            return 0
        max_extent = max(
            (float(t.normalized_x or 0) ** 2 + float(t.normalized_y or 0) ** 2) ** 0.5
            for t in geo_trees
        )
        # Already projected into local meters
        if max_extent > 1.0:
            return 0
        origin = geo_origin_from_points(
            [(float(t.latitude), float(t.longitude)) for t in geo_trees]
        )
        if origin is None:
            return 0
        origin_lat, origin_lng = origin
        fixed = 0
        for tree in geo_trees:
            nx, ny = local_xy_from_latlng(
                float(tree.latitude),
                float(tree.longitude),
                origin_lat,
                origin_lng,
            )
            if tree.normalized_x != nx or tree.normalized_y != ny:
                tree.normalized_x = nx
                tree.normalized_y = ny
                fixed += 1
        if parcel.trees_per_row is None or parcel.trees_per_row == 0:
            by_row: dict[int, int] = {}
            row_number_by_id = {row.id: row.row_number for row in parcel.rows}
            for tree in geo_trees:
                rn = row_number_by_id.get(tree.row_id)
                if rn is None:
                    continue
                by_row[rn] = by_row.get(rn, 0) + 1
            if by_row:
                parcel.trees_per_row = max(by_row.values())
                parcel.row_count = parcel.row_count or len(by_row)
        return fixed


def _merge_row_geometries(drafts: list) -> dict:
    if len(drafts) == 1:
        return drafts[0].geometry
    coords = []
    for d in drafts:
        geom = d.geometry
        if geom.get("type") == "LineString":
            coords.append(geom["coordinates"])
        elif geom.get("type") == "MultiLineString":
            coords.extend(geom["coordinates"])
    return {"type": "MultiLineString", "coordinates": coords}
