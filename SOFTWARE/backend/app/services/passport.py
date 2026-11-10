from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.models.enums import PassportStatus
from app.models.passport import HarvestLot, PassportSnapshot
from app.repositories.farm import FarmRepository
from app.repositories.harvest import HarvestRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.passport import PassportRepository
from app.schemas.passport import (
    DEFAULT_VISIBILITY,
    HarvestLotCreate,
    HarvestLotRead,
    HarvestLotUpdate,
    PublicOrchardSection,
    PublicPassportRead,
    PublicPracticeItem,
    PublicProducerSection,
    PublicProductSection,
)


PASSPORT_SCHEMA_VERSION = "1.0"
DEFAULT_CROP = "Lesnik"


class PassportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.lots = PassportRepository(db)
        self.harvests = HarvestRepository(db)
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)
        self.settings = get_settings()

    # --- Authenticated ------------------------------------------------------------

    def list_lots(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        harvest_id: UUID | None = None,
    ) -> list[HarvestLotRead]:
        return [
            self.to_lot_read(lot)
            for lot in self.lots.list_for_owner(owner_id, parcel_id=parcel_id, harvest_id=harvest_id)
        ]

    def get_lot(self, lot_id: UUID, owner_id: UUID) -> HarvestLotRead:
        return self.to_lot_read(self._get_lot(lot_id, owner_id))

    def get_lot_for_harvest(self, harvest_id: UUID, owner_id: UUID) -> HarvestLotRead | None:
        lot = self.lots.get_by_harvest_for_owner(harvest_id, owner_id)
        return self.to_lot_read(lot) if lot else None

    def create_lot(self, owner_id: UUID, payload: HarvestLotCreate, created_by_id: UUID) -> HarvestLotRead:
        harvest = self.harvests.get_for_owner(payload.harvest_id, owner_id)
        if harvest is None:
            raise NotFoundError("Berba nije pronađena")
        if harvest.parcel_id is None:
            raise AppError("Berba mora biti vezana za parcelu.", status_code=422, code="harvest_no_parcel")

        existing = self.lots.get_by_harvest_for_owner(harvest.id, owner_id)
        if existing is not None:
            raise AppError(
                "Pasoš za ovu berbu već postoji.",
                status_code=409,
                code="lot_exists",
            )

        parcel = self.parcels.get_for_owner(harvest.parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")

        year = harvest.harvested_on.year
        lot_number = self.lots.next_lot_number(year)
        visibility = (
            payload.visibility.model_dump()
            if payload.visibility is not None
            else dict(DEFAULT_VISIBILITY)
        )
        variety = payload.variety
        if variety is None:
            variety = parcel.default_variety
        quantity = payload.quantity
        if quantity is None:
            quantity = harvest.net_quantity or harvest.gross_quantity
        unit = (payload.unit or harvest.unit or "kg").strip() or "kg"
        crop = (payload.crop or DEFAULT_CROP).strip() or DEFAULT_CROP

        lot = HarvestLot(
            farm_id=harvest.farm_id,
            parcel_id=harvest.parcel_id,
            harvest_id=harvest.id,
            lot_number=lot_number,
            harvest_date=harvest.harvested_on,
            quantity=quantity.quantize(Decimal("0.001")) if quantity is not None else None,
            unit=unit,
            crop=crop,
            variety=variety,
            passport_token=_new_token(),
            passport_status=PassportStatus.PUBLISHED,
            visibility=visibility,
            allow_indexing=payload.allow_indexing,
            passport_version=PASSPORT_SCHEMA_VERSION,
            created_by_id=created_by_id,
        )
        self.lots.add(lot)
        self.db.flush()

        if payload.finalize:
            self._finalize(lot, owner_id=owner_id, created_by_id=created_by_id)

        self.db.commit()
        loaded = self.lots.get_for_owner(lot.id, owner_id)
        if loaded is None:
            raise NotFoundError("Lot nije pronađen")
        return self.to_lot_read(loaded)

    def update_lot(self, lot_id: UUID, owner_id: UUID, payload: HarvestLotUpdate) -> HarvestLotRead:
        lot = self._get_lot(lot_id, owner_id)
        if lot.passport_status == PassportStatus.REVOKED:
            raise AppError("Opozvan pasoš se ne može menjati.", status_code=422, code="passport_revoked")
        if lot.passport_status == PassportStatus.FINALIZED:
            raise AppError(
                "Finalizovan pasoš je nepromenljiv. Kreirajte novi lot ako je potrebno.",
                status_code=422,
                code="passport_finalized",
            )
        data = payload.model_dump(exclude_unset=True)
        if "crop" in data and data["crop"] is not None:
            lot.crop = data["crop"].strip() or DEFAULT_CROP
        if "variety" in data:
            lot.variety = (data["variety"] or "").strip() or None
        if "quantity" in data:
            qty = data["quantity"]
            lot.quantity = qty.quantize(Decimal("0.001")) if qty is not None else None
        if "unit" in data and data["unit"] is not None:
            lot.unit = data["unit"].strip() or "kg"
        if "visibility" in data and data["visibility"] is not None:
            lot.visibility = data["visibility"]
        if "allow_indexing" in data and data["allow_indexing"] is not None:
            lot.allow_indexing = data["allow_indexing"]
        self.db.commit()
        return self.to_lot_read(self._get_lot(lot_id, owner_id))

    def finalize_lot(self, lot_id: UUID, owner_id: UUID, created_by_id: UUID) -> HarvestLotRead:
        lot = self._get_lot(lot_id, owner_id)
        if lot.passport_status == PassportStatus.REVOKED:
            raise AppError("Opozvan pasoš se ne može finalizovati.", status_code=422, code="passport_revoked")
        if lot.passport_status == PassportStatus.FINALIZED:
            return self.to_lot_read(lot)
        self._finalize(lot, owner_id=owner_id, created_by_id=created_by_id)
        self.db.commit()
        return self.to_lot_read(self._get_lot(lot_id, owner_id))

    def revoke_lot(self, lot_id: UUID, owner_id: UUID) -> HarvestLotRead:
        lot = self._get_lot(lot_id, owner_id)
        if lot.passport_status == PassportStatus.REVOKED:
            return self.to_lot_read(lot)
        lot.passport_status = PassportStatus.REVOKED
        lot.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.to_lot_read(self._get_lot(lot_id, owner_id))

    def restore_lot(self, lot_id: UUID, owner_id: UUID) -> HarvestLotRead:
        """Re-publish a revoked passport (same token / QR URL)."""
        lot = self._get_lot(lot_id, owner_id)
        if lot.passport_status != PassportStatus.REVOKED:
            return self.to_lot_read(lot)
        lot.passport_status = (
            PassportStatus.FINALIZED if lot.snapshots else PassportStatus.PUBLISHED
        )
        lot.revoked_at = None
        self.db.commit()
        return self.to_lot_read(self._get_lot(lot_id, owner_id))

    # --- Public ------------------------------------------------------------------

    def get_public_passport(self, token: str) -> PublicPassportRead:
        lot = self.lots.get_by_token(token)
        if lot is None:
            raise NotFoundError("Pasoš nije pronađen")
        if lot.passport_status == PassportStatus.REVOKED:
            raise AppError("Ovaj pasoš je opozvan.", status_code=410, code="passport_revoked")
        if lot.passport_status == PassportStatus.DRAFT:
            raise NotFoundError("Pasoš nije pronađen")

        if lot.passport_status == PassportStatus.FINALIZED and lot.snapshots:
            latest = max(lot.snapshots, key=lambda item: item.version)
            return PublicPassportRead.model_validate(latest.payload)

        return self._build_public_passport(lot)

    def public_url_for(self, token: str) -> str:
        base = (getattr(self.settings, "public_app_base_url", None) or "http://localhost:5174").rstrip("/")
        return f"{base}/passport/{token}"

    def qr_api_path(self, token: str) -> str:
        prefix = self.settings.api_prefix.rstrip("/")
        return f"{prefix}/public/passports/{token}/qr.png"

    # --- Serialization -----------------------------------------------------------

    def to_lot_read(self, lot: HarvestLot) -> HarvestLotRead:
        snapshots = list(lot.snapshots or [])
        snapshot_version = max((s.version for s in snapshots), default=None)
        return HarvestLotRead(
            id=lot.id,
            created_at=lot.created_at,
            updated_at=lot.updated_at,
            farm_id=lot.farm_id,
            parcel_id=lot.parcel_id,
            harvest_id=lot.harvest_id,
            lot_number=lot.lot_number,
            harvest_date=lot.harvest_date,
            quantity=lot.quantity,
            unit=lot.unit,
            crop=lot.crop,
            variety=lot.variety,
            passport_token=lot.passport_token,
            passport_status=lot.passport_status,
            visibility=lot.visibility or dict(DEFAULT_VISIBILITY),
            allow_indexing=lot.allow_indexing,
            passport_version=lot.passport_version,
            finalized_at=lot.finalized_at,
            revoked_at=lot.revoked_at,
            created_by_id=lot.created_by_id,
            public_url=self.public_url_for(lot.passport_token),
            qr_url=self.qr_api_path(lot.passport_token),
            parcel_name=lot.parcel.name if lot.parcel is not None else None,
            farm_name=lot.farm.name if lot.farm is not None else None,
            producer_name=_producer_name(lot.farm),
            parcel_location=_parcel_location(lot.farm),
            varieties=_variety_names(lot.parcel),
            snapshot_version=snapshot_version,
        )

    # --- Internals ---------------------------------------------------------------

    def _finalize(self, lot: HarvestLot, *, owner_id: UUID, created_by_id: UUID) -> None:
        # Ensure relationships loaded for assembly.
        loaded = self.lots.get_for_owner(lot.id, owner_id)
        if loaded is None:
            raise NotFoundError("Lot nije pronađen")
        loaded.passport_status = PassportStatus.FINALIZED
        loaded.finalized_at = datetime.now(timezone.utc)
        loaded.passport_version = PASSPORT_SCHEMA_VERSION
        public = self._build_public_passport(loaded)
        existing_versions = [s.version for s in (loaded.snapshots or [])]
        version = (max(existing_versions) + 1) if existing_versions else 1
        snapshot = PassportSnapshot(
            harvest_lot_id=loaded.id,
            version=version,
            passport_version=PASSPORT_SCHEMA_VERSION,
            payload=public.model_dump(mode="json"),
            created_by_id=created_by_id,
        )
        self.lots.add_snapshot(snapshot)
        self.db.flush()
        self.db.refresh(loaded)


    def _build_public_passport(self, lot: HarvestLot) -> PublicPassportRead:
        visibility = {**DEFAULT_VISIBILITY, **(lot.visibility or {})}
        farm = lot.farm
        parcel = lot.parcel

        producer = None
        if visibility.get("producer", True):
            producer = PublicProducerSection(
                name=_producer_name(farm),
                country=(farm.country if farm is not None else None) or "Srbija",
                logo_url=farm.logo_url if farm is not None else None,
            )

        orchard = None
        if visibility.get("orchard", True) or visibility.get("location", True):
            location = None
            if visibility.get("location", True) and farm is not None:
                # Municipality / general location only — never lat/lng or private address.
                location = farm.location_name
            orchard = PublicOrchardSection(
                farm_name=farm.name if farm is not None and visibility.get("orchard", True) else None,
                location=location,
                parcel_name=parcel.name if parcel is not None and visibility.get("orchard", True) else None,
            )

        product = None
        if visibility.get("product", True):
            show_qty = visibility.get("quantity", True)
            product = PublicProductSection(
                crop=lot.crop,
                variety=lot.variety,
                varieties=_variety_names(parcel),
                harvest_year=lot.harvest_date.year,
                harvest_date=lot.harvest_date,
                quantity=lot.quantity if show_qty else None,
                unit=lot.unit if show_qty else None,
            )

        practices = None
        if visibility.get("production_practices", True) and parcel is not None:
            practices = _public_practices(parcel)

        trace: list[str] = []
        if producer and producer.name:
            trace.append(producer.name)
        if orchard and orchard.farm_name:
            trace.append(orchard.farm_name)
        if orchard and orchard.parcel_name:
            trace.append(orchard.parcel_name)
        if practices:
            trace.append("Proizvodne prakse")
        trace.append(f"Lot {lot.lot_number}")

        return PublicPassportRead(
            lot_number=lot.lot_number,
            passport_version=lot.passport_version or PASSPORT_SCHEMA_VERSION,
            passport_status=lot.passport_status,
            created_at=lot.created_at,
            finalized=lot.passport_status == PassportStatus.FINALIZED,
            allow_indexing=lot.allow_indexing,
            producer=producer,
            orchard=orchard,
            product=product,
            production_practices=practices,
            traceability=trace,
            metadata={
                "lot_number": lot.lot_number,
                "passport_created_at": lot.created_at.isoformat(),
                "passport_version": lot.passport_version or PASSPORT_SCHEMA_VERSION,
                "finalized_at": lot.finalized_at.isoformat() if lot.finalized_at else None,
            },
        )

    def _get_lot(self, lot_id: UUID, owner_id: UUID) -> HarvestLot:
        lot = self.lots.get_for_owner(lot_id, owner_id)
        if lot is None:
            raise NotFoundError("Lot nije pronađen")
        return lot


def _producer_name(farm: Any) -> str | None:
    if farm is None:
        return None
    if getattr(farm, "public_producer_name", None):
        return farm.public_producer_name
    owner = getattr(farm, "owner", None)
    if owner is not None and getattr(owner, "full_name", None):
        return owner.full_name
    return None


def _parcel_location(farm: Any) -> str | None:
    if farm is None:
        return None
    return getattr(farm, "location_name", None)


def _variety_names(parcel: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        text = (value or "").strip()
        key = text.casefold()
        if not text or key in seen:
            return
        seen.add(key)
        names.append(text)

    raw = getattr(parcel, "varieties", None) or []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                add(str(item.get("name") or ""))
            elif isinstance(item, str):
                add(item)
    add(getattr(parcel, "default_variety", None))
    return names


def _new_token() -> str:
    # 32 bytes → ~43 url-safe chars; unguessable and non-sequential.
    return secrets.token_urlsafe(32)


def _public_practices(parcel: Any) -> list[PublicPracticeItem]:
    items: list[PublicPracticeItem] = []
    method = getattr(parcel, "production_method", None)
    if method is not None:
        label = "Organska proizvodnja" if str(method.value) == "organic" else "Konvencionalna proizvodnja"
        items.append(PublicPracticeItem(key="production_method", label="Način proizvodnje", value=label))

    organic_scope = getattr(parcel, "organic_scope", None)
    if organic_scope is not None and str(organic_scope.value) not in {"none", "None"}:
        scope_map = {
            "entire_parcel": "Cela parcela",
            "part_of_parcel": "Deo parcele",
        }
        items.append(
            PublicPracticeItem(
                key="organic_scope",
                label="Obuhvat organske proizvodnje",
                value=scope_map.get(str(organic_scope.value), str(organic_scope.value)),
            )
        )

    if getattr(parcel, "has_irrigation", False):
        irrigation_type = getattr(parcel, "irrigation_type", None)
        type_label = {
            "drip": "Kap po kap",
            "sprinkler": "Kišenje",
            "microsprinkler": "Mikrokišenje",
            "other": "Drugo",
        }.get(str(irrigation_type.value) if irrigation_type else "", "Da")
        water = getattr(parcel, "water_source", None)
        value = type_label
        if water:
            value = f"{type_label} · izvor: {water}"
        items.append(PublicPracticeItem(key="irrigation", label="Navodnjavanje", value=value))
    else:
        items.append(PublicPracticeItem(key="irrigation", label="Navodnjavanje", value="Bez sistema za navodnjavanje"))

    # High-level practice markers only — no product SKUs, rates, or costs.
    items.append(
        PublicPracticeItem(
            key="fertilization",
            label="Ishrana bilja",
            value="Vođena prema planu gazdinstva",
        )
    )
    items.append(
        PublicPracticeItem(
            key="plant_protection",
            label="Zaštita bilja",
            value="Vođena prema planu gazdinstva",
        )
    )
    return items
