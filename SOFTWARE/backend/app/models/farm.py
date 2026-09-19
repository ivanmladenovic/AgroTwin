from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Farm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "farms"

    owner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    owner: Mapped[User] = relationship("User", back_populates="farms")
    parcels: Mapped[list[Parcel]] = relationship("Parcel", back_populates="farm")
