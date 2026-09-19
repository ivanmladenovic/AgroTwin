from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.activity import Activity
from app.models.cost import Cost
from app.models.enums import ActivityStatus, ScopeType
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.activity import ActivityRepository
from app.repositories.catalog import CatalogRepository
from app.repositories.cost import CostRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.row import RowRepository
from app.repositories.tree import TreeRepository
from app.schemas.activity import ActivityCreate, ActivityLineItem, ActivityRead, ActivityUpdate
from app.schemas.catalog import CatalogItemRead
from app.schemas.cost import CostCreate, CostItemRead, CostSummaryRead, NamedAmount, QuantityLineRead, YearAmount


class ActivityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = ActivityRepository(db)
        self.costs = CostRepository(db)
        self.catalogs = CatalogRepository(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)

    def list_activities(
        self,
        owner_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        activity_type_id: UUID | None = None,
        scope_type: ScopeType | None = None,
        parcel_id: UUID | None = None,
        row_id: UUID | None = None,
        tree_id: UUID | None = None,
        status: ActivityStatus | None = None,
        limit: int | None = None,
    ) -> list[ActivityRead]:
        records = self.activities.list_for_owner(
            owner_id,
            date_from=date_from,
            date_to=date_to,
            activity_type_id=activity_type_id,
            scope_type=scope_type,
            parcel_id=parcel_id,
            row_id=row_id,
            tree_id=tree_id,
            status=status,
            limit=limit,
        )
        return [self.to_activity_read(item) for item in records]

    def get_activity(self, activity_id: UUID, owner_id: UUID) -> Activity:
        activity = self.activities.get_for_owner(activity_id, owner_id)
        if activity is None:
            raise NotFoundError("Aktivnost nije pronađena")
        return activity

    def create_activity(self, owner_id: UUID, payload: ActivityCreate, created_by_id: UUID) -> Activity:
        activity_type = self.catalogs.get_activity_type(payload.activity_type_id)
        if activity_type is None:
            raise NotFoundError("Tip aktivnosti nije pronađen")
        farm_id, parcel_id, row_id, tree_id, extra_row_ids = self._resolve_scope(owner_id, payload)
        if payload.status is not None:
            status = payload.status
        elif payload.performed_on > date.today():
            status = ActivityStatus.PLANNED
        else:
            status = ActivityStatus.COMPLETED
        line_items = self._normalize_line_items(payload)
        first_item = line_items[0] if line_items else None
        activity = Activity(
            activity_type_id=activity_type.id,
            title=(payload.title or activity_type.name).strip(),
            description=payload.description,
            performed_on=payload.performed_on,
            status=status,
            quantity=first_item.quantity if first_item else payload.quantity,
            unit=(first_item.unit.strip() if first_item and first_item.unit else None)
            or (payload.unit.strip() if payload.unit else None),
            line_items=[item.model_dump(mode="json") for item in line_items],
            extra_row_ids=extra_row_ids,
            notes=payload.notes,
            created_by_id=created_by_id,
            scope_type=payload.scope_type,
            farm_id=farm_id,
            parcel_id=parcel_id,
            row_id=row_id,
            tree_id=tree_id,
        )
        self.activities.add(activity)
        self.db.flush()
        self._add_costs_from_line_items(activity, line_items, created_by_id)
        if payload.cost_amount and payload.cost_amount > 0 and not any(_is_eur_unit(item.unit) for item in line_items):
            self._add_inline_cost(activity, payload.cost_amount, created_by_id, description=activity.title)
        self.db.commit()
        loaded = self.activities.get_for_owner(activity.id, owner_id)
        assert loaded is not None
        return loaded

    def update_activity(self, activity_id: UUID, owner_id: UUID, payload: ActivityUpdate) -> Activity:
        activity = self.get_activity(activity_id, owner_id)
        if payload.status is not None:
            activity.status = payload.status
        if payload.performed_on is not None:
            activity.performed_on = payload.performed_on
        if payload.notes is not None:
            activity.notes = payload.notes
        if payload.description is not None:
            activity.description = payload.description
        self.db.commit()
        self.db.refresh(activity)
        loaded = self.activities.get_for_owner(activity.id, owner_id)
        assert loaded is not None
        return loaded

    def add_cost(self, activity_id: UUID, owner_id: UUID, payload: CostCreate, created_by_id: UUID) -> Cost:
        activity = self.get_activity(activity_id, owner_id)
        category = self.catalogs.get_cost_category(payload.cost_category_id)
        if category is None:
            raise NotFoundError("Kategorija troška nije pronađena")
        cost = Cost(
            amount=payload.amount,
            currency=payload.currency.upper(),
            incurred_on=payload.incurred_on or activity.performed_on,
            description=payload.description.strip(),
            cost_category_id=category.id,
            activity_id=activity.id,
            notes=payload.notes,
            receipt_filename=payload.receipt_filename.strip() if payload.receipt_filename else None,
            created_by_id=created_by_id,
            scope_type=activity.scope_type,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            row_id=activity.row_id,
            tree_id=activity.tree_id,
        )
        self.costs.add(cost)
        self.db.flush()
        cost_id = cost.id
        self.db.commit()
        loaded = self.costs.get_for_owner(cost_id, owner_id)
        if loaded is None:
            raise NotFoundError("Trošak nije pronađen")
        return loaded

    def cost_summary(self, owner_id: UUID, parcel_id: UUID | None = None) -> CostSummaryRead:
        if parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
        today = date.today()
        year_start = date(today.year, 1, 1)
        month_start = date(today.year, today.month, 1)
        total = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id)
        year_total = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_from=year_start)
        month_total = self.costs.sum_for_owner(owner_id, parcel_id=parcel_id, date_from=month_start)
        active_trees = self.trees.active_count(owner_id, parcel_id)
        area = self.parcels.total_area_hectares(owner_id, parcel_id)
        cost_per_tree = (total / active_trees).quantize(Decimal("0.01")) if active_trees else None
        cost_per_hectare = (total / area).quantize(Decimal("0.01")) if area else None
        yearly = self.costs.yearly_totals(owner_id, parcel_id=parcel_id)
        years = sorted(yearly) or [today.year]
        by_year = [
            YearAmount(year=year, amount=yearly.get(year, Decimal("0")))
            for year in range(years[0], today.year + 1)
        ]
        return CostSummaryRead(
            total_costs=total,
            current_year_costs=year_total,
            current_month_costs=month_total,
            cost_per_tree=cost_per_tree,
            cost_per_hectare=cost_per_hectare,
            active_tree_count=active_trees,
            area_hectares=area,
            by_category=[
                NamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
                for item, amount in self.costs.totals_by_category(owner_id, parcel_id=parcel_id)
            ],
            by_activity_type=[
                NamedAmount(id=item.id, name=item.name, slug=item.slug, amount=amount)
                for item, amount in self.costs.totals_by_activity_type(owner_id, parcel_id=parcel_id)
            ],
            by_year=by_year,
            parcel_id=parcel_id,
        )

    def list_costs(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[CostItemRead]:
        if parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
        records = self.costs.list_for_owner(
            owner_id, parcel_id=parcel_id, date_from=date_from, date_to=date_to
        )
        return [self.to_cost_read(item) for item in records]

    def to_activity_read(self, activity: Activity) -> ActivityRead:
        parcel_name, row_number, tree_public_id = self._scope_labels(
            activity.parcel_id, activity.row_id, activity.tree_id
        )
        costs = [self.to_cost_read(item) for item in activity.costs]
        total = sum((item.amount for item in activity.costs), Decimal("0"))
        currency = costs[0].currency if costs else "EUR"
        row_ids, row_numbers = self._activity_rows(activity)
        return ActivityRead(
            id=activity.id,
            created_at=activity.created_at,
            updated_at=activity.updated_at,
            activity_type=CatalogItemRead.model_validate(activity.activity_type),
            title=activity.title,
            description=activity.description,
            performed_on=activity.performed_on,
            status=activity.status,
            quantity=activity.quantity,
            unit=activity.unit,
            line_items=self._read_line_items(activity),
            notes=activity.notes,
            scope_type=activity.scope_type,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            row_id=activity.row_id,
            row_ids=row_ids,
            row_numbers=row_numbers,
            tree_id=activity.tree_id,
            parcel_name=parcel_name,
            row_number=row_numbers[0] if row_numbers else row_number,
            tree_public_id=tree_public_id,
            costs=costs,
            total_cost=total,
            currency=currency,
        )

    def to_cost_read(self, cost: Cost) -> CostItemRead:
        parcel_name, row_number, tree_public_id = self._scope_labels(cost.parcel_id, cost.row_id, cost.tree_id)
        activity_title = cost.activity.title if cost.activity is not None else None
        activity_type_name = (
            cost.activity.activity_type.name if cost.activity is not None and cost.activity.activity_type else None
        )
        line_items = (
            [
                QuantityLineRead(quantity=item.quantity, unit=item.unit)
                for item in self._read_line_items(cost.activity)
            ]
            if cost.activity is not None
            else []
        )
        return CostItemRead(
            id=cost.id,
            created_at=cost.created_at,
            updated_at=cost.updated_at,
            activity_id=cost.activity_id,
            description=cost.description,
            cost_category=CatalogItemRead.model_validate(cost.cost_category),
            amount=cost.amount,
            currency=cost.currency,
            incurred_on=cost.incurred_on,
            notes=cost.notes,
            receipt_filename=cost.receipt_filename,
            scope_type=cost.scope_type,
            farm_id=cost.farm_id,
            parcel_id=cost.parcel_id,
            row_id=cost.row_id,
            tree_id=cost.tree_id,
            activity_title=activity_title,
            activity_type_name=activity_type_name,
            activity_line_items=line_items,
            parcel_name=parcel_name,
            row_number=row_number,
            tree_public_id=tree_public_id,
        )

    def _resolve_scope(
        self, owner_id: UUID, payload: ActivityCreate
    ) -> tuple[UUID, UUID, UUID | None, UUID | None, list[str]]:
        parcel = self.parcels.get_for_owner(payload.parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        row_id: UUID | None = None
        tree_id: UUID | None = None
        extra_row_ids: list[str] = []
        if payload.scope_type in {ScopeType.ROW, ScopeType.TREE}:
            requested = list(dict.fromkeys(payload.row_ids or ([payload.row_id] if payload.row_id else [])))
            if payload.scope_type == ScopeType.TREE:
                requested = [payload.row_id] if payload.row_id else requested
            if not requested:
                raise AppError("Red je obavezan za ovaj obuhvat", status_code=422, code="invalid_scope")
            resolved: list[UUID] = []
            for item_id in requested:
                row = self.rows.get_for_parcel(parcel.id, item_id)
                if row is None:
                    raise NotFoundError("Red nije pronađen")
                resolved.append(row.id)
            row_id = resolved[0]
            extra_row_ids = [str(item) for item in resolved]
        if payload.scope_type == ScopeType.TREE:
            if payload.tree_id is None:
                raise AppError("Stablo je obavezno za ovaj obuhvat", status_code=422, code="invalid_scope")
            found = self.trees.get_for_parcel(parcel.id, payload.tree_id)
            if found is None:
                raise NotFoundError("Stablo nije pronađeno")
            tree, _row_number = found
            if row_id is not None and tree.row_id != row_id:
                raise AppError("Stablo ne pripada izabranom redu", status_code=422, code="invalid_scope")
            tree_id = tree.id
            extra_row_ids = [str(row_id)] if row_id else []
        return parcel.farm_id, parcel.id, row_id, tree_id, extra_row_ids

    def _normalize_line_items(self, payload: ActivityCreate) -> list[ActivityLineItem]:
        items = [
            item
            for item in payload.line_items
            if item.quantity is not None or (item.unit or "").strip()
        ]
        if items:
            return items
        if payload.quantity is not None or (payload.unit or "").strip():
            return [ActivityLineItem(quantity=payload.quantity, unit=payload.unit)]
        return []

    def _read_line_items(self, activity: Activity) -> list[ActivityLineItem]:
        raw = activity.line_items or []
        items: list[ActivityLineItem] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            items.append(
                ActivityLineItem(
                    quantity=item.get("quantity"),
                    unit=item.get("unit"),
                )
            )
        if items:
            return items
        if activity.quantity is not None or activity.unit:
            return [ActivityLineItem(quantity=activity.quantity, unit=activity.unit)]
        return []

    def _activity_rows(self, activity: Activity) -> tuple[list[UUID], list[int]]:
        stored: list[UUID] = []
        for item in activity.extra_row_ids or []:
            try:
                stored.append(item if isinstance(item, UUID) else UUID(str(item)))
            except ValueError:
                continue
        if activity.row_id and activity.row_id not in stored:
            stored.insert(0, activity.row_id)
        pairs: list[tuple[UUID, int]] = []
        for item_id in stored:
            row = self.db.get(Row, item_id)
            if row is not None:
                pairs.append((item_id, row.row_number))
        pairs.sort(key=lambda item: item[1])
        return [item[0] for item in pairs], [item[1] for item in pairs]

    def _add_costs_from_line_items(
        self, activity: Activity, line_items: list[ActivityLineItem], created_by_id: UUID
    ) -> None:
        for item in line_items:
            if not _is_eur_unit(item.unit) or item.quantity is None or item.quantity <= 0:
                continue
            self._add_inline_cost(activity, item.quantity, created_by_id, description=activity.title)

    def _add_inline_cost(
        self,
        activity: Activity,
        amount: Decimal,
        created_by_id: UUID,
        description: str | None = None,
    ) -> None:
        categories = self.catalogs.list_cost_categories()
        category = self.catalogs.get_cost_category_by_slug("other") or (categories[0] if categories else None)
        if category is None:
            raise AppError("Kategorija troška nije pronađena", status_code=422, code="missing_cost_category")
        cost = Cost(
            amount=amount,
            currency="EUR",
            incurred_on=activity.performed_on,
            description=description or activity.title,
            cost_category_id=category.id,
            activity_id=activity.id,
            created_by_id=created_by_id,
            scope_type=activity.scope_type,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            row_id=activity.row_id,
            tree_id=activity.tree_id,
        )
        self.costs.add(cost)

    def _scope_labels(
        self,
        parcel_id: UUID | None,
        row_id: UUID | None,
        tree_id: UUID | None,
    ) -> tuple[str | None, int | None, str | None]:
        parcel_name = None
        row_number = None
        tree_public_id = None
        if parcel_id is not None:
            parcel = self.db.get(Parcel, parcel_id)
            parcel_name = parcel.name if parcel else None
        if row_id is not None:
            row = self.db.get(Row, row_id)
            row_number = row.row_number if row else None
        if tree_id is not None:
            tree = self.db.get(Tree, tree_id)
            tree_public_id = tree.public_id if tree else None
        return parcel_name, row_number, tree_public_id


def _is_eur_unit(unit: str | None) -> bool:
    value = (unit or "").strip().upper().replace("€", "EUR")
    return value in {"EUR", "EURO"}
