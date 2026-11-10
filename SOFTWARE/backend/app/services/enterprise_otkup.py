"""Enterprise otkup: supplier prices and purchase ledger (read/write for plan writers)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.enterprise.access import EnterpriseAccess
from app.models.enterprise import (
    EnterpriseAuditEvent,
    EnterpriseParcelAssignment,
    EnterprisePurchase,
    EnterpriseSupplierLink,
    EnterpriseSupplierPrice,
)
from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseAuditAction,
    EnterprisePurchaseCurrency,
    EnterpriseQuantityBasis,
    EnterpriseRelationshipStatus,
)
from app.models.farm import Farm
from app.models.harvest import HarvestEvent
from app.models.user import User
from app.schemas.enterprise import (
    EnterpriseOtkupOverview,
    EnterpriseOtkupSupplierRow,
    EnterprisePurchaseCreate,
    EnterprisePurchaseRead,
    EnterprisePurchaseUpdate,
    EnterpriseSupplierPriceRead,
    EnterpriseSupplierPriceUpsert,
)
from app.services.enterprise import EnterpriseService


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class EnterpriseOtkupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.access = EnterpriseAccess(db)
        self.enterprise = EnterpriseService(db)

    def overview(
        self, user: User, organization_id: UUID, *, season_year: int | None = None
    ) -> EnterpriseOtkupOverview:
        self.access.require_reader(user, organization_id)
        year = season_year or date.today().year
        links = [
            link
            for link in self._active_links(organization_id)
        ]
        farm_ids = [link.farm_id for link in links]
        farms = {
            f.id: f
            for f in self.db.scalars(select(Farm).where(Farm.id.in_(farm_ids))).all()
        } if farm_ids else {}
        prices = {
            p.farm_id: p
            for p in self.db.scalars(
                select(EnterpriseSupplierPrice).where(
                    EnterpriseSupplierPrice.organization_id == organization_id,
                    EnterpriseSupplierPrice.season_year == year,
                )
            ).all()
        }
        # Assigned parcels per farm (explicit assignments only).
        assignment_rows = (
            self.db.execute(
                select(
                    EnterpriseParcelAssignment.farm_id,
                    EnterpriseParcelAssignment.parcel_id,
                ).where(
                    self.access.active_assignment_filter(organization_id),
                    EnterpriseParcelAssignment.status == EnterpriseAssignmentStatus.ACTIVE,
                )
            ).all()
            if farm_ids
            else []
        )
        parcels_by_farm: dict[UUID, list[UUID]] = {}
        all_assigned_parcel_ids: list[UUID] = []
        for farm_id, parcel_id in assignment_rows:
            parcels_by_farm.setdefault(farm_id, []).append(parcel_id)
            all_assigned_parcel_ids.append(parcel_id)

        # Harvest from producer journal on assigned parcels.
        harvest_by_farm: dict[UUID, dict] = {}
        if all_assigned_parcel_ids:
            harvest_rows = self.db.execute(
                select(
                    HarvestEvent.parcel_id,
                    func.count().label("cnt"),
                    func.sum(HarvestEvent.gross_quantity).label("gross"),
                    func.sum(HarvestEvent.net_quantity).label("net"),
                    func.max(HarvestEvent.harvested_on).label("last_on"),
                )
                .where(
                    HarvestEvent.parcel_id.in_(all_assigned_parcel_ids),
                    extract("year", HarvestEvent.harvested_on) == year,
                )
                .group_by(HarvestEvent.parcel_id)
            ).all()
            parcel_to_farm = {
                pid: fid for fid, pids in parcels_by_farm.items() for pid in pids
            }
            for row in harvest_rows:
                farm_id = parcel_to_farm.get(row.parcel_id)
                if farm_id is None:
                    continue
                bucket = harvest_by_farm.setdefault(
                    farm_id,
                    {
                        "cnt": 0,
                        "gross": Decimal("0"),
                        "net": Decimal("0"),
                        "last_on": None,
                        "parcels_with_harvest": set(),
                        "has_gross": False,
                        "has_net": False,
                    },
                )
                bucket["cnt"] += int(row.cnt or 0)
                bucket["parcels_with_harvest"].add(row.parcel_id)
                if row.gross is not None:
                    bucket["gross"] += Decimal(str(row.gross))
                    bucket["has_gross"] = True
                if row.net is not None:
                    bucket["net"] += Decimal(str(row.net))
                    bucket["has_net"] = True
                if row.last_on and (
                    bucket["last_on"] is None or row.last_on > bucket["last_on"]
                ):
                    bucket["last_on"] = row.last_on

        purchase_rows = (
            self.db.execute(
                select(
                    EnterprisePurchase.farm_id,
                    func.count().label("cnt"),
                    func.coalesce(func.sum(EnterprisePurchase.quantity_kg), 0).label("qty"),
                    func.coalesce(func.sum(EnterprisePurchase.total_amount), 0).label("amt"),
                    func.max(EnterprisePurchase.purchased_on).label("last_on"),
                )
                .where(
                    EnterprisePurchase.organization_id == organization_id,
                    extract("year", EnterprisePurchase.purchased_on) == year,
                )
                .group_by(EnterprisePurchase.farm_id)
            ).all()
            if farm_ids
            else []
        )
        by_farm = {row.farm_id: row for row in purchase_rows}

        currency_totals: dict[str, Decimal] = {}
        if farm_ids:
            for cur, total in self.db.execute(
                select(
                    EnterprisePurchase.currency,
                    func.coalesce(func.sum(EnterprisePurchase.total_amount), 0),
                )
                .where(
                    EnterprisePurchase.organization_id == organization_id,
                    extract("year", EnterprisePurchase.purchased_on) == year,
                )
                .group_by(EnterprisePurchase.currency)
            ).all():
                currency_totals[str(cur)] = Decimal(str(total))

        suppliers: list[EnterpriseOtkupSupplierRow] = []
        notes: list[str] = []
        for link in links:
            farm = farms.get(link.farm_id)
            display, _, _ = self.enterprise._producer_display(farm)
            price = prices.get(link.farm_id)
            agg = by_farm.get(link.farm_id)
            qty = Decimal(str(agg.qty)) if agg and agg.cnt else None
            amt = Decimal(str(agg.amt)) if agg and agg.cnt else None
            harvest = harvest_by_farm.get(link.farm_id)
            assigned = parcels_by_farm.get(link.farm_id, [])
            harvest_gross = (
                harvest["gross"] if harvest and harvest["has_gross"] else None
            )
            harvest_net = harvest["net"] if harvest and harvest["has_net"] else None
            suppliers.append(
                EnterpriseOtkupSupplierRow(
                    farm_id=link.farm_id,
                    producer_display_name=display,
                    farm_name=farm.name if farm else "—",
                    assigned_parcels=len(assigned),
                    parcels_with_harvest=(
                        len(harvest["parcels_with_harvest"]) if harvest else 0
                    ),
                    harvest_gross_kg=harvest_gross,
                    harvest_net_kg=harvest_net,
                    harvest_event_count=int(harvest["cnt"]) if harvest else 0,
                    last_harvested_on=harvest["last_on"] if harvest else None,
                    currency=(
                        EnterprisePurchaseCurrency(price.currency)
                        if price
                        else None
                    ),
                    price_bruto_per_kg=price.price_bruto_per_kg if price else None,
                    price_neto_per_kg=price.price_neto_per_kg if price else None,
                    price_notes=price.notes if price else None,
                    purchase_count=int(agg.cnt) if agg else 0,
                    purchased_quantity_kg=qty,
                    purchased_amount=amt,
                    last_purchased_on=agg.last_on if agg else None,
                    total_quantity_kg=qty,
                    total_amount=amt,
                )
            )
        suppliers.sort(
            key=lambda row: (row.producer_display_name or row.farm_name or "").lower()
        )

        purchase_count = sum(s.purchase_count for s in suppliers)
        purchased_qty = None
        if purchase_count:
            purchased_qty = sum(
                (s.purchased_quantity_kg or Decimal("0") for s in suppliers),
                Decimal("0"),
            )

        suppliers_with_harvest = sum(
            1 for s in suppliers if s.harvest_event_count > 0
        )
        harvest_net_total = None
        harvest_gross_total = None
        if suppliers_with_harvest:
            if any(s.harvest_net_kg is not None for s in suppliers):
                harvest_net_total = sum(
                    (s.harvest_net_kg or Decimal("0") for s in suppliers),
                    Decimal("0"),
                )
            if any(s.harvest_gross_kg is not None for s in suppliers):
                harvest_gross_total = sum(
                    (s.harvest_gross_kg or Decimal("0") for s in suppliers),
                    Decimal("0"),
                )
            if harvest_net_total is None and harvest_gross_total is None:
                notes.append(
                    f"Postoje unosi berbe za {year}, ali bez količine (neto/bruto) — "
                    "prikazano kao nedostupno, ne kao nula."
                )
        elif suppliers:
            notes.append(
                f"Nema evidentirane berbe na dodeljenim parcelama za {year}."
            )

        if not suppliers:
            notes.append("Nema povezanih dobavljača — povežite ih u Dobavljači.")

        return EnterpriseOtkupOverview(
            season_year=year,
            suppliers=suppliers,
            purchase_count=purchase_count,
            total_quantity_kg=purchased_qty,
            purchased_quantity_kg=purchased_qty,
            harvest_gross_kg=harvest_gross_total,
            harvest_net_kg=harvest_net_total,
            suppliers_with_harvest=suppliers_with_harvest,
            totals_by_currency=currency_totals,
            notes=notes,
        )

    def upsert_price(
        self, user: User, organization_id: UUID, payload: EnterpriseSupplierPriceUpsert
    ) -> EnterpriseSupplierPriceRead:
        self.access.require_plan_writer(user, organization_id)
        self._require_linked_farm(organization_id, payload.farm_id)
        if payload.price_bruto_per_kg is None and payload.price_neto_per_kg is None:
            raise AppError("Unesite barem jednu cenu (bruto ili neto) po kg.")

        existing = self.db.scalars(
            select(EnterpriseSupplierPrice).where(
                EnterpriseSupplierPrice.organization_id == organization_id,
                EnterpriseSupplierPrice.farm_id == payload.farm_id,
                EnterpriseSupplierPrice.season_year == payload.season_year,
            )
        ).first()
        if existing is None:
            existing = EnterpriseSupplierPrice(
                organization_id=organization_id,
                farm_id=payload.farm_id,
                season_year=payload.season_year,
            )
            self.db.add(existing)

        existing.currency = payload.currency.value
        existing.price_bruto_per_kg = payload.price_bruto_per_kg
        existing.price_neto_per_kg = payload.price_neto_per_kg
        existing.notes = payload.notes
        existing.updated_by_id = user.id
        self.db.flush()
        self._audit(
            organization_id,
            user.id,
            EnterpriseAuditAction.SUPPLIER_PRICE_UPSERTED.value,
            "enterprise_supplier_price",
            existing.id,
            {"farm_id": str(payload.farm_id), "season_year": payload.season_year},
        )
        return self._price_read(existing)

    def list_purchases(
        self,
        user: User,
        organization_id: UUID,
        *,
        season_year: int | None = None,
        farm_id: UUID | None = None,
    ) -> list[EnterprisePurchaseRead]:
        self.access.require_reader(user, organization_id)
        year = season_year or date.today().year
        stmt = select(EnterprisePurchase).where(
            EnterprisePurchase.organization_id == organization_id,
            extract("year", EnterprisePurchase.purchased_on) == year,
        )
        if farm_id is not None:
            self._require_linked_farm(organization_id, farm_id)
            stmt = stmt.where(EnterprisePurchase.farm_id == farm_id)
        stmt = stmt.order_by(
            EnterprisePurchase.purchased_on.desc(),
            EnterprisePurchase.created_at.desc(),
        )
        return [self._purchase_read(row) for row in self.db.scalars(stmt).all()]

    def create_purchase(
        self, user: User, organization_id: UUID, payload: EnterprisePurchaseCreate
    ) -> EnterprisePurchaseRead:
        self.access.require_plan_writer(user, organization_id)
        self._require_linked_farm(organization_id, payload.farm_id)
        year = payload.purchased_on.year
        price_card = self.db.scalars(
            select(EnterpriseSupplierPrice).where(
                EnterpriseSupplierPrice.organization_id == organization_id,
                EnterpriseSupplierPrice.farm_id == payload.farm_id,
                EnterpriseSupplierPrice.season_year == year,
            )
        ).first()

        currency = payload.currency
        if currency is None:
            if price_card is not None:
                currency = EnterprisePurchaseCurrency(price_card.currency)
            else:
                currency = EnterprisePurchaseCurrency.RSD

        unit_price = payload.unit_price_per_kg
        if unit_price is None:
            if price_card is None:
                raise AppError(
                    "Nema definisane cene za ovog dobavljača u sezoni — unesite cenu po kg ručno."
                )
            unit_price = (
                price_card.price_bruto_per_kg
                if payload.quantity_basis == EnterpriseQuantityBasis.BRUTO
                else price_card.price_neto_per_kg
            )
            if unit_price is None:
                raise AppError(
                    f"Nema cene za {payload.quantity_basis.value} — definišite je ili unesite cenu ručno."
                )

        total = payload.total_amount
        if total is None:
            total = _money(payload.quantity_kg * unit_price)

        row = EnterprisePurchase(
            organization_id=organization_id,
            farm_id=payload.farm_id,
            purchased_on=payload.purchased_on,
            quantity_kg=payload.quantity_kg,
            quantity_basis=payload.quantity_basis.value,
            currency=currency.value,
            unit_price_per_kg=_price(unit_price),
            total_amount=_money(total),
            price_bruto_per_kg=price_card.price_bruto_per_kg if price_card else None,
            price_neto_per_kg=price_card.price_neto_per_kg if price_card else None,
            notes=payload.notes,
            created_by_id=user.id,
        )
        self.db.add(row)
        self.db.flush()
        self._audit(
            organization_id,
            user.id,
            EnterpriseAuditAction.PURCHASE_CREATED.value,
            "enterprise_purchase",
            row.id,
            {"farm_id": str(payload.farm_id), "total_amount": str(row.total_amount)},
        )
        return self._purchase_read(row)

    def update_purchase(
        self,
        user: User,
        organization_id: UUID,
        purchase_id: UUID,
        payload: EnterprisePurchaseUpdate,
    ) -> EnterprisePurchaseRead:
        self.access.require_plan_writer(user, organization_id)
        row = self._get_purchase(organization_id, purchase_id)
        data = payload.model_dump(exclude_unset=True)
        if "quantity_basis" in data and data["quantity_basis"] is not None:
            data["quantity_basis"] = data["quantity_basis"].value
        if "currency" in data and data["currency"] is not None:
            data["currency"] = data["currency"].value
        for key, value in data.items():
            setattr(row, key, value)
        if payload.quantity_kg is not None or payload.unit_price_per_kg is not None:
            if payload.total_amount is None:
                row.total_amount = _money(row.quantity_kg * row.unit_price_per_kg)
        if payload.unit_price_per_kg is not None:
            row.unit_price_per_kg = _price(row.unit_price_per_kg)
        if payload.total_amount is not None:
            row.total_amount = _money(row.total_amount)
        self.db.flush()
        self._audit(
            organization_id,
            user.id,
            EnterpriseAuditAction.PURCHASE_UPDATED.value,
            "enterprise_purchase",
            row.id,
            {},
        )
        return self._purchase_read(row)

    def delete_purchase(
        self, user: User, organization_id: UUID, purchase_id: UUID
    ) -> None:
        self.access.require_plan_writer(user, organization_id)
        row = self._get_purchase(organization_id, purchase_id)
        self._audit(
            organization_id,
            user.id,
            EnterpriseAuditAction.PURCHASE_DELETED.value,
            "enterprise_purchase",
            row.id,
            {"farm_id": str(row.farm_id)},
        )
        self.db.delete(row)
        self.db.flush()

    def _active_links(self, organization_id: UUID) -> list[EnterpriseSupplierLink]:
        return list(
            self.db.scalars(
                select(EnterpriseSupplierLink)
                .where(
                    EnterpriseSupplierLink.organization_id == organization_id,
                    EnterpriseSupplierLink.status == EnterpriseRelationshipStatus.ACTIVE,
                )
                .order_by(EnterpriseSupplierLink.assigned_at.desc())
            ).all()
        )

    def _require_linked_farm(self, organization_id: UUID, farm_id: UUID) -> None:
        link = self.db.scalars(
            select(EnterpriseSupplierLink).where(
                EnterpriseSupplierLink.organization_id == organization_id,
                EnterpriseSupplierLink.farm_id == farm_id,
                EnterpriseSupplierLink.status == EnterpriseRelationshipStatus.ACTIVE,
            )
        ).first()
        if link is None:
            raise ForbiddenError("Dobavljač nije povezan sa ovom organizacijom.")

    def _get_purchase(self, organization_id: UUID, purchase_id: UUID) -> EnterprisePurchase:
        row = self.db.scalars(
            select(EnterprisePurchase).where(
                EnterprisePurchase.id == purchase_id,
                EnterprisePurchase.organization_id == organization_id,
            )
        ).first()
        if row is None:
            raise NotFoundError("Otkup nije pronađen.")
        return row

    def _price_read(self, row: EnterpriseSupplierPrice) -> EnterpriseSupplierPriceRead:
        farm = self.db.get(Farm, row.farm_id)
        display, _, _ = self.enterprise._producer_display(farm)
        return EnterpriseSupplierPriceRead(
            id=row.id,
            organization_id=row.organization_id,
            farm_id=row.farm_id,
            season_year=row.season_year,
            currency=EnterprisePurchaseCurrency(row.currency),
            price_bruto_per_kg=row.price_bruto_per_kg,
            price_neto_per_kg=row.price_neto_per_kg,
            notes=row.notes,
            producer_display_name=display,
            farm_name=farm.name if farm else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _purchase_read(self, row: EnterprisePurchase) -> EnterprisePurchaseRead:
        farm = self.db.get(Farm, row.farm_id)
        display, _, _ = self.enterprise._producer_display(farm)
        return EnterprisePurchaseRead(
            id=row.id,
            organization_id=row.organization_id,
            farm_id=row.farm_id,
            purchased_on=row.purchased_on,
            quantity_kg=row.quantity_kg,
            quantity_basis=EnterpriseQuantityBasis(row.quantity_basis),
            currency=EnterprisePurchaseCurrency(row.currency),
            unit_price_per_kg=row.unit_price_per_kg,
            total_amount=row.total_amount,
            price_bruto_per_kg=row.price_bruto_per_kg,
            price_neto_per_kg=row.price_neto_per_kg,
            notes=row.notes,
            producer_display_name=display,
            farm_name=farm.name if farm else None,
            created_by_id=row.created_by_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _audit(
        self,
        organization_id: UUID,
        actor_user_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID,
        details: dict,
    ) -> None:
        self.db.add(
            EnterpriseAuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        )
