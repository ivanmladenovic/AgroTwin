from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import WellLocation, pg_enum


class Parcel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parcels"
    __table_args__ = (UniqueConstraint("farm_id", "code", name="uq_parcels_farm_code"),)

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    maps_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trees_per_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_spacing_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    tree_spacing_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    default_variety: Mapped[str | None] = mapped_column(String(128), nullable=True)
    varieties: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    default_planting_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starting_tree_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    well_location: Mapped[WellLocation | None] = mapped_column(
        pg_enum(WellLocation, "well_location"),
        nullable=True,
    )
    well_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    well_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    farm: Mapped[Farm] = relationship("Farm", back_populates="parcels")
    rows: Mapped[list[Row]] = relationship(
        "Row",
        back_populates="parcel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    trees: Mapped[list[Tree]] = relationship(
        "Tree",
        back_populates="parcel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
