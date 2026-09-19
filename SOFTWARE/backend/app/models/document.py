from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ATTACHMENT_ENTITY_TYPE,
    AttachmentEntityType,
    DocumentStatus,
    KnowledgeCategory,
    pg_enum,
)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[AttachmentEntityType] = mapped_column(
        ATTACHMENT_ENTITY_TYPE,
        nullable=False,
        index=True,
    )
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled document")
    category: Mapped[KnowledgeCategory] = mapped_column(
        pg_enum(KnowledgeCategory, "knowledge_category"),
        default=KnowledgeCategory.OTHER,
        nullable=False,
        index=True,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="sr")
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    pages: Mapped[list["KnowledgePage"]] = relationship(
        "KnowledgePage",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    assets: Mapped[list["KnowledgeAsset"]] = relationship(
        "KnowledgeAsset",
        back_populates="document",
        cascade="all, delete-orphan",
    )
