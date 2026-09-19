from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import HealthStatus, TreeStatus, pg_enum


class Tree(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trees"
    __table_args__ = (
        UniqueConstraint("parcel_id", "public_id", name="uq_trees_parcel_public_id"),
        UniqueConstraint("row_id", "position_in_row", name="uq_trees_row_position"),
    )

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orchard_rows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    position_in_row: Mapped[int] = mapped_column(Integer, nullable=False)
    planting_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variety: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[TreeStatus] = mapped_column(
        pg_enum(TreeStatus, "tree_status"),
        default=TreeStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    health_status: Mapped[HealthStatus] = mapped_column(
        pg_enum(HealthStatus, "health_status"),
        default=HealthStatus.HEALTHY,
        nullable=False,
        index=True,
    )
    normalized_x: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    normalized_y: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    parcel: Mapped[Parcel] = relationship("Parcel", back_populates="trees")
    row: Mapped[Row] = relationship("Row", back_populates="trees")
    disease_cases: Mapped[list[DiseaseCase]] = relationship("DiseaseCase", back_populates="tree")
