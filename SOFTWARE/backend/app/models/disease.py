from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DiseaseCaseStatus, DiseaseCategory, DiseaseSeverity, pg_enum


class DiseaseCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disease_cases"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orchard_rows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tree_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("trees.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[DiseaseCategory] = mapped_column(
        pg_enum(DiseaseCategory, "disease_category"),
        default=DiseaseCategory.UNKNOWN,
        nullable=False,
        index=True,
    )
    severity: Mapped[DiseaseSeverity] = mapped_column(
        pg_enum(DiseaseSeverity, "disease_severity"),
        default=DiseaseSeverity.MEDIUM,
        nullable=False,
    )
    status: Mapped[DiseaseCaseStatus] = mapped_column(
        pg_enum(DiseaseCaseStatus, "disease_case_status"),
        default=DiseaseCaseStatus.OPEN,
        nullable=False,
        index=True,
    )
    detected_on: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    tree: Mapped["Tree | None"] = relationship("Tree", back_populates="disease_cases")
    observations: Mapped[list[DiseaseObservation]] = relationship(
        "DiseaseObservation",
        back_populates="disease_case",
        cascade="all, delete-orphan",
    )


class DiseaseObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disease_observations"

    disease_case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    disease_case: Mapped[DiseaseCase] = relationship("DiseaseCase", back_populates="observations")
