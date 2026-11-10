from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ComplianceReportFormat, ComplianceReportType, pg_enum

if TYPE_CHECKING:
    from app.models.farm import Farm
    from app.models.user import User


class ComplianceReportDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Reusable report definition (seeded; not hard-coded only in PDF templates)."""

    __tablename__ = "compliance_report_definitions"
    __table_args__ = (UniqueConstraint("type", "version", name="uq_compliance_report_def_type_version"),)

    type: Mapped[ComplianceReportType] = mapped_column(
        pg_enum(ComplianceReportType, "compliance_report_type"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_source: Mapped[str] = mapped_column(String(128), nullable=False)
    template: Mapped[str] = mapped_column(String(128), nullable=False, default="tabular_v1")
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    default_filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_in_default_package: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ComplianceReportRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit log of generated compliance reports (retained; never auto-deleted)."""

    __tablename__ = "compliance_report_runs"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[ComplianceReportType] = mapped_column(
        pg_enum(ComplianceReportType, "compliance_report_type"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[ComplianceReportFormat] = mapped_column(
        pg_enum(ComplianceReportFormat, "compliance_report_format"),
        nullable=False,
    )
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    parcel_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    definition_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("compliance_report_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    definition_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    generated_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    farm: Mapped[Farm] = relationship("Farm")
    generated_by: Mapped[User | None] = relationship("User")
