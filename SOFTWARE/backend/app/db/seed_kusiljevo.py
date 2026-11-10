"""Idempotent presentation metadata for the real Kusiljevo parcel.

Journal history, costs, harvests and health cases are grower-entered —
this seed only updates farm/parcel profile fields.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import WellLocation
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.user import User

KUSILJEVO = "Kusiljevo"


def seed_kusiljevo_presentation(db: Session, user: User, farm: Farm) -> None:
    parcel = db.scalars(select(Parcel).where(Parcel.farm_id == farm.id, Parcel.name == KUSILJEVO)).first()
    if parcel is None:
        return

    farm.name = "Voćnjak Kusiljevo"
    farm.location_name = "Kusiljevo, Srbija"
    farm.description = "Zasad lesnika Tonda di Giffoni sa oprašivačima, 26 redova × 73 mesta."
    farm.area_hectares = parcel.area_hectares or Decimal("4.7500")
    user.full_name = "Ivan Mladenović"
    parcel.notes = (
        "Zasad iz 2022. na blagoj padini iznad sela. Glavna sorta Tonda di Giffoni, "
        "oprašivači Tonda Gentile Romana i Nocchione. Sistem kap po kap od prve godine."
    )
    if parcel.well_location is None:
        parcel.well_location = WellLocation.WEST
        parcel.well_x = Decimal("-6.0000")
        parcel.well_y = Decimal("62.5000")
    db.flush()
