from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Row(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orchard_rows"
    __table_args__ = (UniqueConstraint("parcel_id", "row_number", name="uq_orchard_rows_parcel_number"),)

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tree_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variety: Mapped[str | None] = mapped_column(String(128), nullable=True)
    planting_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_organic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # GeoJSON LineString or MultiLineString in WGS84 (map editor). Null for schematic-only rows.
    geometry: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    segment_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    parcel: Mapped[Parcel] = relationship("Parcel", back_populates="rows")
    trees: Mapped[list[Tree]] = relationship("Tree", back_populates="row")
