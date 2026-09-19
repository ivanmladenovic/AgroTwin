from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError

from app.models.enums import AttachmentEntityType, ScopeType, TreeStatus
from app.models.harvest import HarvestEvent
from app.models.parcel import Parcel
from app.models.tree import Tree
from app.repositories.harvest import HarvestRepository, trees_by_id
from app.repositories.parcel import ParcelRepository
from app.repositories.photo import PhotoRepository
from app.repositories.row import RowRepository
from app.repositories.tree import TreeRepository
from app.schemas.harvest import (
    HarvestEventCreate,
    HarvestEventRead,
    HarvestEventUpdate,
    HarvestQualitySummary,
    HarvestRowSummary,
    HarvestTimelinePoint,
    HarvestTreeSummary,
    ParcelProductionRead,
    ProductionComparison,
    QualityAverage,
    QualityCategoryShare,
)
from app.schemas.report import OptionalAmount, YearChange
from app.services.disease import DiseaseService
from app.services.harvest_calc import (
    MISSING_PREVIOUS_YEAR,
    PARCEL_TOTAL_NOTE,
    HarvestMeasure,
    available_production_years,
    first_last_dates,
    parcel_scope_only,
    quality_from_measures,
    quantity_kg,
    timeline_points,
    total_kg,
    validate_quantities,
    year_bounds,
    yield_per_hectare,
    yield_per_tree,
)
from app.services.parcel_report_calc import change_direction, change_tone, percent_change


class HarvestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.harvests = HarvestRepository(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)
        self.photos = PhotoRepository(db)
        self.diseases = DiseaseService(db)

    def list_harvests(self, owner_id: UUID, parcel_id: UUID, year: int) -> list[HarvestEventRead]:
        parcel = self._parcel(owner_id, parcel_id)
        start, end = year_bounds(year)
        events = self.harvests.list_for_parcel(owner_id, parcel.id, date_from=start, date_to=end)
        return [self.to_harvest_read(item, include_photos=False) for item in events]

    def get_harvest(self, owner_id: UUID, parcel_id: UUID, harvest_id: UUID) -> HarvestEventRead:
        event = self._get_event(owner_id, parcel_id, harvest_id)
        return self.to_harvest_read(event, include_photos=True)

    def create_harvest(self, owner_id: UUID, parcel_id: UUID, payload: HarvestEventCreate, created_by_id: UUID) -> HarvestEvent:
        parcel = self._parcel(owner_id, parcel_id)
        validate_quantities(payload.gross_quantity, payload.loss_quantity)
        farm_id, row_id, tree_id = self._resolve_scope(owner_id, parcel.id, payload.scope_type, payload.row_id, payload.tree_id)
        event = HarvestEvent(
            harvested_on=payload.harvested_on,
            scope_type=payload.scope_type,
            farm_id=farm_id,
            parcel_id=parcel.id,
            row_id=row_id,
            tree_id=tree_id,
            gross_quantity=payload.gross_quantity,
            loss_quantity=payload.loss_quantity,
            unit=(payload.unit or "kg").strip() or "kg",
            moisture_percent=payload.moisture_percent,
            quality_category=payload.quality_category,
            damaged_percent=payload.damaged_percent,
            empty_nuts_percent=payload.empty_nuts_percent,
            foreign_material_percent=payload.foreign_material_percent,
            size_or_caliber=payload.size_or_caliber.strip() if payload.size_or_caliber else None,
            notes=payload.notes.strip() if payload.notes else None,
            activity_id=payload.activity_id,
            created_by_id=created_by_id,
        )
        self.harvests.add(event)
        self.db.flush()
        self.db.commit()
        self.db.refresh(event)
        loaded = self.harvests.get_for_owner(event.id, owner_id)
        assert loaded is not None
        return loaded

    def update_harvest(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        harvest_id: UUID,
        payload: HarvestEventUpdate,
    ) -> HarvestEvent:
        event = self._get_event(owner_id, parcel_id, harvest_id)
        gross = payload.gross_quantity if payload.gross_quantity is not None else event.gross_quantity
        loss = payload.loss_quantity if payload.loss_quantity is not None else event.loss_quantity
        validate_quantities(gross, loss)
        scope_type = payload.scope_type or event.scope_type
        row_id = payload.row_id if "row_id" in payload.model_fields_set else event.row_id
        tree_id = payload.tree_id if "tree_id" in payload.model_fields_set else event.tree_id
        if payload.scope_type is not None or "row_id" in payload.model_fields_set or "tree_id" in payload.model_fields_set:
            _farm_id, row_id, tree_id = self._resolve_scope(owner_id, parcel_id, scope_type, row_id, tree_id)
            event.scope_type = scope_type
            event.row_id = row_id
            event.tree_id = tree_id
        event.gross_quantity = gross
        event.loss_quantity = loss
        if payload.harvested_on is not None:
            event.harvested_on = payload.harvested_on
        if payload.unit is not None:
            event.unit = payload.unit.strip() or "kg"
        if "moisture_percent" in payload.model_fields_set:
            event.moisture_percent = payload.moisture_percent
        if "damaged_percent" in payload.model_fields_set:
            event.damaged_percent = payload.damaged_percent
        if "empty_nuts_percent" in payload.model_fields_set:
            event.empty_nuts_percent = payload.empty_nuts_percent
        if "foreign_material_percent" in payload.model_fields_set:
            event.foreign_material_percent = payload.foreign_material_percent
        if payload.clear_quality_category:
            event.quality_category = None
        elif "quality_category" in payload.model_fields_set:
            event.quality_category = payload.quality_category
        if "size_or_caliber" in payload.model_fields_set:
            event.size_or_caliber = payload.size_or_caliber.strip() if payload.size_or_caliber else None
        if "notes" in payload.model_fields_set:
            event.notes = payload.notes.strip() if payload.notes else None
        if payload.clear_activity_id:
            event.activity_id = None
        elif "activity_id" in payload.model_fields_set:
            event.activity_id = payload.activity_id
        self.db.commit()
        self.db.refresh(event)
        loaded = self.harvests.get_for_owner(event.id, owner_id)
        assert loaded is not None
        return loaded

    def delete_harvest(self, owner_id: UUID, parcel_id: UUID, harvest_id: UUID) -> None:
        event = self._get_event(owner_id, parcel_id, harvest_id)
        self.harvests.delete(event)
        self.db.commit()

    def get_production(self, owner_id: UUID, parcel_id: UUID, year: int) -> ParcelProductionRead:
        parcel = self._parcel(owner_id, parcel_id)
        start, end = year_bounds(year)
        previous_year = year - 1
        prev_start, prev_end = year_bounds(previous_year)
        events = self.harvests.list_for_parcel(owner_id, parcel.id, date_from=start, date_to=end)
        previous_events = self.harvests.list_for_parcel(owner_id, parcel.id, date_from=prev_start, date_to=prev_end)
        measures = [self._measure(item) for item in events]
        previous_measures = [self._measure(item) for item in previous_events]
        parcel_measures = parcel_scope_only(measures)
        previous_parcel = parcel_scope_only(previous_measures)
        active_trees = self.trees.active_count(owner_id, parcel.id)
        area = parcel.area_hectares
        net = total_kg(parcel_measures, "net")
        gross = total_kg(parcel_measures, "gross")
        loss = total_kg(parcel_measures, "loss")
        first, last = first_last_dates(parcel_measures)
        per_ha = yield_per_hectare(net, area)
        per_tree = yield_per_tree(net, active_trees) if active_trees > 0 else None
        previous_net = total_kg(previous_parcel, "net")
        previous_per_ha = yield_per_hectare(previous_net, area)
        photos = self._latest_photos(events)
        quality = quality_from_measures(parcel_measures)
        reads = [self.to_harvest_read(item, include_photos=False, parcel_name=parcel.name) for item in reversed(events)]
        return ParcelProductionRead(
            parcel_id=parcel.id,
            parcel_name=parcel.name,
            year=year,
            area_hectares=area,
            active_trees=active_trees,
            available_years=available_production_years(
                self.harvests.years_for_parcel(parcel.id),
                selected_year=year,
                current_year=date.today().year,
                planting_year=parcel.default_planting_year,
            ),
            recorded=len(events) > 0,
            parcel_total_recorded=len(parcel_measures) > 0,
            measurement_note=PARCEL_TOTAL_NOTE,
            total_gross_quantity=self._optional(gross),
            total_loss_quantity=self._optional(loss),
            total_net_yield=self._optional(net),
            harvest_event_count=len(parcel_measures) if parcel_measures else None,
            all_event_count=len(events),
            first_harvest_date=first,
            last_harvest_date=last,
            yield_per_hectare=self._optional(per_ha),
            yield_per_tree=self._optional(per_tree),
            yield_per_tree_denominator="active_trees" if per_tree is not None else None,
            events=reads,
            timeline=[HarvestTimelinePoint(**point) for point in timeline_points(parcel_measures)],
            row_summary=self._row_summary(parcel.id, events),
            tree_summary=self._tree_summary(parcel.id, events),
            quality_summary=self._quality_schema(quality),
            comparison=self._comparison(year, previous_year, net, previous_net, per_ha, previous_per_ha, len(parcel_measures), len(previous_parcel)),
            photos=photos,
        )

    def harvests_csv(self, owner_id: UUID, parcel_id: UUID, year: int) -> str:
        records = self.list_harvests(owner_id, parcel_id, year)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "date",
                "scope",
                "row",
                "tree",
                "gross_quantity",
                "loss_quantity",
                "net_quantity",
                "unit",
                "moisture_percent",
                "quality_category",
                "notes",
            ]
        )
        for item in records:
            writer.writerow(
                [
                    item.harvested_on.isoformat(),
                    item.scope_type.value,
                    item.row_number if item.row_number is not None else "",
                    item.tree_public_id or "",
                    item.gross_quantity,
                    item.loss_quantity,
                    item.net_quantity,
                    item.unit,
                    item.moisture_percent if item.moisture_percent is not None else "",
                    item.quality_category.value if item.quality_category else "",
                    item.notes or "",
                ]
            )
        return output.getvalue()

    def to_harvest_read(
        self,
        event: HarvestEvent,
        *,
        include_photos: bool = False,
        parcel_name: str | None = None,
    ) -> HarvestEventRead:
        row_number = None
        tree_public_id = None
        tree_status = None
        if parcel_name is None and event.parcel_id:
            parcel = self.db.get(Parcel, event.parcel_id)
            parcel_name = parcel.name if parcel else None
        if event.row_id:
            row = self.rows.get_by_id(event.row_id)
            row_number = row.row_number if row else None
        if event.tree_id:
            tree = self.db.get(Tree, event.tree_id)
            if tree is not None:
                tree_public_id = tree.public_id
                tree_status = tree.status.value
        photos = []
        if include_photos:
            photos = [
                self.diseases.to_photo_read(item)
                for item in self.photos.list_for_entity(AttachmentEntityType.HARVEST_EVENT, event.id)
            ]
        return HarvestEventRead(
            id=event.id,
            created_at=event.created_at,
            updated_at=event.updated_at,
            harvested_on=event.harvested_on,
            scope_type=event.scope_type,
            farm_id=event.farm_id,
            parcel_id=event.parcel_id,
            row_id=event.row_id,
            tree_id=event.tree_id,
            parcel_name=parcel_name,
            row_number=row_number,
            tree_public_id=tree_public_id,
            tree_status=tree_status,
            location_label=self._location_label(event.scope_type, parcel_name, row_number, tree_public_id),
            gross_quantity=event.gross_quantity,
            loss_quantity=event.loss_quantity,
            net_quantity=event.net_quantity,
            unit=event.unit,
            gross_kg=quantity_kg(event.gross_quantity, event.unit),
            loss_kg=quantity_kg(event.loss_quantity, event.unit),
            net_kg=quantity_kg(event.net_quantity, event.unit),
            moisture_percent=event.moisture_percent,
            quality_category=event.quality_category,
            damaged_percent=event.damaged_percent,
            empty_nuts_percent=event.empty_nuts_percent,
            foreign_material_percent=event.foreign_material_percent,
            size_or_caliber=event.size_or_caliber,
            notes=event.notes,
            activity_id=event.activity_id,
            created_by_id=event.created_by_id,
            created_by_name=event.created_by.full_name if event.created_by else None,
            photos=photos,
        )

    def _parcel(self, owner_id: UUID, parcel_id: UUID):
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel

    def _get_event(self, owner_id: UUID, parcel_id: UUID, harvest_id: UUID) -> HarvestEvent:
        event = self.harvests.get_for_owner(harvest_id, owner_id)
        if event is None or event.parcel_id != parcel_id:
            raise NotFoundError("Berba nije pronađena")
        return event

    def _resolve_scope(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        scope_type: ScopeType,
        row_id: UUID | None,
        tree_id: UUID | None,
    ) -> tuple[UUID, UUID | None, UUID | None]:
        parcel = self._parcel(owner_id, parcel_id)
        if scope_type == ScopeType.PARCEL:
            return parcel.farm_id, None, None
        if scope_type == ScopeType.ROW:
            if row_id is None:
                raise AppError("Berba reda zahteva red.", status_code=422)
            row = self.rows.get_for_parcel(parcel.id, row_id)
            if row is None:
                raise AppError("Izabrani red ne pripada ovoj parceli.", status_code=422)
            return parcel.farm_id, row.id, None
        if scope_type == ScopeType.TREE:
            if tree_id is None:
                raise AppError("Berba stabla zahteva stablo.", status_code=422)
            found = self.trees.get_for_parcel(parcel.id, tree_id)
            if found is None:
                raise AppError("Izabrano stablo ne pripada ovoj parceli.", status_code=422)
            tree, _row_number = found
            if row_id is not None and row_id != tree.row_id:
                raise AppError("Izabrano stablo ne pripada izabranom redu.", status_code=422)
            return parcel.farm_id, tree.row_id, tree.id
        raise AppError("Obuhvat berbe nije podržan.", status_code=422)

    def _measure(self, event: HarvestEvent) -> HarvestMeasure:
        return HarvestMeasure(
            scope_type=event.scope_type.value if isinstance(event.scope_type, ScopeType) else str(event.scope_type),
            harvested_on=event.harvested_on,
            gross=event.gross_quantity,
            loss=event.loss_quantity,
            unit=event.unit,
            moisture_percent=event.moisture_percent,
            damaged_percent=event.damaged_percent,
            empty_nuts_percent=event.empty_nuts_percent,
            foreign_material_percent=event.foreign_material_percent,
            quality_category=event.quality_category,
            row_id=event.row_id,
            tree_id=event.tree_id,
        )

    def _row_summary(self, parcel_id: UUID, events: list[HarvestEvent]) -> list[HarvestRowSummary]:
        grouped: dict[UUID, dict[str, Decimal | int]] = defaultdict(lambda: {"net_kg": Decimal("0"), "count": 0})
        for event in events:
            if event.scope_type != ScopeType.ROW or event.row_id is None:
                continue
            kg = quantity_kg(event.net_quantity, event.unit)
            if kg is None:
                continue
            grouped[event.row_id]["net_kg"] = Decimal(str(grouped[event.row_id]["net_kg"])) + kg
            grouped[event.row_id]["count"] = int(grouped[event.row_id]["count"]) + 1
        if not grouped:
            return []
        active_by_row = self._active_trees_by_row(parcel_id)
        summaries = []
        for row_id, payload in grouped.items():
            row = self.rows.get_by_id(row_id)
            active = active_by_row.get(row_id, 0)
            net_kg = Decimal(str(payload["net_kg"]))
            summaries.append(
                HarvestRowSummary(
                    row_id=row_id,
                    row_number=row.row_number if row else 0,
                    harvest_event_count=int(payload["count"]),
                    net_kg=net_kg,
                    active_trees=active,
                    yield_per_tree=self._optional(yield_per_tree(net_kg, active) if active > 0 else None),
                )
            )
        return sorted(summaries, key=lambda item: item.row_number)

    def _tree_summary(self, parcel_id: UUID, events: list[HarvestEvent]) -> list[HarvestTreeSummary]:
        grouped: dict[UUID, dict[str, Decimal | int]] = defaultdict(lambda: {"net_kg": Decimal("0"), "count": 0})
        for event in events:
            if event.scope_type != ScopeType.TREE or event.tree_id is None:
                continue
            kg = quantity_kg(event.net_quantity, event.unit)
            if kg is None:
                continue
            grouped[event.tree_id]["net_kg"] = Decimal(str(grouped[event.tree_id]["net_kg"])) + kg
            grouped[event.tree_id]["count"] = int(grouped[event.tree_id]["count"]) + 1
        if not grouped:
            return []
        trees = trees_by_id(self.db, list(grouped))
        summaries = []
        for tree_id, payload in grouped.items():
            tree = trees.get(tree_id)
            if tree is None:
                continue
            row = self.rows.get_by_id(tree.row_id)
            summaries.append(
                HarvestTreeSummary(
                    tree_id=tree.id,
                    public_id=tree.public_id,
                    row_id=tree.row_id,
                    row_number=row.row_number if row else 0,
                    tree_status=tree.status.value,
                    health_status=tree.health_status.value,
                    net_kg=Decimal(str(payload["net_kg"])),
                    harvest_event_count=int(payload["count"]),
                )
            )
        return sorted(summaries, key=lambda item: (-item.net_kg, item.public_id))

    def _active_trees_by_row(self, parcel_id: UUID) -> dict[UUID, int]:
        stmt = (
            select(Tree.row_id, func.count())
            .where(Tree.parcel_id == parcel_id, Tree.status == TreeStatus.ACTIVE)
            .group_by(Tree.row_id)
        )
        return {row_id: int(count) for row_id, count in self.db.execute(stmt).all()}

    def _latest_photos(self, events: list[HarvestEvent]):
        if not events:
            return []
        pairs = [(AttachmentEntityType.HARVEST_EVENT, event.id) for event in events]
        photos = self.photos.list_for_entities(pairs)[:8]
        return [self.diseases.to_photo_read(item) for item in photos]

    def _quality_schema(self, payload: dict) -> HarvestQualitySummary:
        def average(data: dict) -> QualityAverage:
            return QualityAverage(
                available=bool(data.get("available")),
                value=data.get("value"),
                method=data.get("method"),
                sample_count=int(data.get("sample_count") or 0),
            )

        return HarvestQualitySummary(
            recorded=bool(payload.get("recorded")),
            moisture=average(payload.get("moisture") or {}),
            damaged=average(payload.get("damaged") or {}),
            empty_nuts=average(payload.get("empty_nuts") or {}),
            foreign_material=average(payload.get("foreign_material") or {}),
            categories=[
                QualityCategoryShare(
                    category=item["category"],
                    net_kg=item["net_kg"],
                    event_count=item["event_count"],
                )
                for item in payload.get("categories") or []
            ],
        )

    def _comparison(
        self,
        year: int,
        previous_year: int,
        net: Decimal | None,
        previous_net: Decimal | None,
        per_ha: Decimal | None,
        previous_per_ha: Decimal | None,
        event_count: int,
        previous_event_count: int,
    ) -> ProductionComparison:
        previous_recorded = previous_net is not None
        current_recorded = net is not None
        available = previous_recorded and current_recorded
        previous_count = previous_event_count if previous_recorded else None
        return ProductionComparison(
            available=available,
            previous_year=previous_year,
            previous_net_yield=self._optional(previous_net),
            previous_yield_per_hectare=self._optional(previous_per_ha if previous_recorded else None),
            previous_harvest_event_count=previous_count,
            net_yield_change=self._change("yield_kg", net, previous_net),
            yield_per_hectare_change=self._change("yield_kg", per_ha, previous_per_ha if previous_recorded else None),
            harvest_event_count_change=self._change(
                "activities_completed",
                Decimal(event_count) if current_recorded else None,
                Decimal(previous_event_count) if previous_recorded else None,
            ),
            message=None if available else MISSING_PREVIOUS_YEAR,
        )

    def _change(self, key: str, current: Decimal | None, previous: Decimal | None) -> YearChange:
        available = current is not None and previous is not None
        direction = change_direction(current, previous) if available else None
        return YearChange(
            available=available,
            previous=previous if available else None,
            percent=percent_change(current, previous) if available else None,
            direction=direction,
            tone=change_tone(key, direction) if available else None,
        )

    def _optional(self, value: Decimal | None) -> OptionalAmount:
        return OptionalAmount(available=value is not None, value=value)

    def _location_label(
        self,
        scope_type: ScopeType,
        parcel_name: str | None,
        row_number: int | None,
        tree_public_id: str | None,
    ) -> str:
        if scope_type == ScopeType.TREE and tree_public_id:
            return tree_public_id
        if scope_type == ScopeType.ROW and row_number is not None:
            return f"Red {str(row_number).zfill(2)}"
        return parcel_name or "Parcela"
