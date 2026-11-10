from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SoilLabExtractionStatus, SoilLabVerificationStatus, pg_enum

_SOIL_LAB_EXTRACTION_STATUS = pg_enum(SoilLabExtractionStatus, "soil_lab_extraction_status")
_SOIL_LAB_VERIFICATION_STATUS = pg_enum(SoilLabVerificationStatus, "soil_lab_verification_status")


class SoilLabAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded laboratory soil report (PDF/image) for a parcel sample point."""

    __tablename__ = "soil_lab_analyses"

    activity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    tree_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("trees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sampled_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    analysis_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    laboratory_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_depth_from_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sample_depth_to_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[SoilLabExtractionStatus] = mapped_column(
        _SOIL_LAB_EXTRACTION_STATUS,
        default=SoilLabExtractionStatus.PENDING,
        nullable=False,
    )
    verification_status: Mapped[SoilLabVerificationStatus] = mapped_column(
        _SOIL_LAB_VERIFICATION_STATUS,
        default=SoilLabVerificationStatus.NEEDS_REVIEW,
        nullable=False,
        index=True,
    )
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    activity: Mapped["Activity"] = relationship("Activity", back_populates="soil_analyses")
    results: Mapped[list[SoilLabResult]] = relationship(
        "SoilLabResult",
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SoilLabResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One structured parameter extracted (or manually entered) from a lab report."""

    __tablename__ = "soil_lab_results"

    analysis_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("soil_lab_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameter_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_parameter_name: Mapped[str] = mapped_column(String(512), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    depth_from_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    depth_to_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[SoilLabVerificationStatus] = mapped_column(
        _SOIL_LAB_VERIFICATION_STATUS,
        default=SoilLabVerificationStatus.EXTRACTED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped[SoilLabAnalysis] = relationship("SoilLabAnalysis", back_populates="results")
