from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeBaseItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_base_items"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subsection: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="sr")
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class KnowledgePage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number", name="uq_knowledge_pages_document_page"),)

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    image_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="pages")


class KnowledgeAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_assets"

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="page")
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    document: Mapped["Document"] = relationship("Document", back_populates="assets")
