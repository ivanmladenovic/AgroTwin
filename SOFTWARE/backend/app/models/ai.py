from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_conversations"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parcel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[list[AIMessage]] = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AIMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    structured_refs: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    conversation: Mapped[AIConversation] = relationship("AIConversation", back_populates="messages")
