from __future__ import annotations

from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiseaseAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disease_analyses"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    disease_case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("disease_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    photo_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="SET NULL"),
        nullable=True,
    )
    likely_issue: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observed_symptoms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    possible_alternatives: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    recommended_inspection: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_next_step: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_sources: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    observed_facts: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty_notes: Mapped[str] = mapped_column(Text, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
