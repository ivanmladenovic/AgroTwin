from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentUser, DBSession
from app.core.config import get_settings
from app.passport.qr import generate_qr_png
from app.passport.rate_limit import passport_rate_limiter
from app.schemas.passport import HarvestLotCreate, HarvestLotRead, HarvestLotUpdate, PublicPassportRead
from app.services.passport import PassportService

router = APIRouter(tags=["passport"])


@router.get("/harvest-lots", response_model=list[HarvestLotRead])
def list_harvest_lots(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
    harvest_id: UUID | None = None,
) -> list[HarvestLotRead]:
    return PassportService(db).list_lots(
        current_user.id, parcel_id=parcel_id, harvest_id=harvest_id
    )


@router.post("/harvest-lots", response_model=HarvestLotRead, status_code=201)
def create_harvest_lot(
    payload: HarvestLotCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> HarvestLotRead:
    return PassportService(db).create_lot(current_user.id, payload, current_user.id)


@router.get("/harvest-lots/{lot_id}", response_model=HarvestLotRead)
def get_harvest_lot(lot_id: UUID, current_user: CurrentUser, db: DBSession) -> HarvestLotRead:
    return PassportService(db).get_lot(lot_id, current_user.id)


@router.patch("/harvest-lots/{lot_id}", response_model=HarvestLotRead)
def update_harvest_lot(
    lot_id: UUID,
    payload: HarvestLotUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> HarvestLotRead:
    return PassportService(db).update_lot(lot_id, current_user.id, payload)


@router.post("/harvest-lots/{lot_id}/finalize", response_model=HarvestLotRead)
def finalize_harvest_lot(lot_id: UUID, current_user: CurrentUser, db: DBSession) -> HarvestLotRead:
    return PassportService(db).finalize_lot(lot_id, current_user.id, current_user.id)


@router.post("/harvest-lots/{lot_id}/revoke", response_model=HarvestLotRead)
def revoke_harvest_lot(lot_id: UUID, current_user: CurrentUser, db: DBSession) -> HarvestLotRead:
    return PassportService(db).revoke_lot(lot_id, current_user.id)


@router.post("/harvest-lots/{lot_id}/restore", response_model=HarvestLotRead)
def restore_harvest_lot(lot_id: UUID, current_user: CurrentUser, db: DBSession) -> HarvestLotRead:
    return PassportService(db).restore_lot(lot_id, current_user.id)


@router.get("/harvests/{harvest_id}/lot", response_model=HarvestLotRead | None)
def get_lot_for_harvest(
    harvest_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> HarvestLotRead | None:
    return PassportService(db).get_lot_for_harvest(harvest_id, current_user.id)


# --- Public (no auth) ------------------------------------------------------------

public_router = APIRouter(prefix="/public/passports", tags=["public-passport"])


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@public_router.get("/{token}", response_model=PublicPassportRead)
def get_public_passport(
    token: str, request: Request, response: Response, db: DBSession
) -> PublicPassportRead:
    passport_rate_limiter.check(_client_key(request), get_settings())
    response.headers["Cache-Control"] = "no-store"
    return PassportService(db).get_public_passport(token)


@public_router.get("/{token}/qr.png")
def get_public_passport_qr(token: str, request: Request, db: DBSession) -> Response:
    passport_rate_limiter.check(_client_key(request), get_settings())
    service = PassportService(db)
    # Validate token exists and is not revoked before emitting QR.
    passport = service.get_public_passport(token)
    url = service.public_url_for(token)
    png = generate_qr_png(url)
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": f'inline; filename="{passport.lot_number}-qr.png"',
    }
    return Response(content=png, media_type="image/png", headers=headers)
