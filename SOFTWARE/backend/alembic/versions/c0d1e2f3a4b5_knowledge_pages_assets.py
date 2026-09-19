"""knowledge pages, assets and retrieval metadata

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-09-15 10:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("page_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("image_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("source_kind", sa.String(length=32), server_default="user", nullable=False))
    op.add_column("documents", sa.Column("language", sa.String(length=8), server_default="sr", nullable=False))
    op.add_column("documents", sa.Column("parser_version", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("ocr_version", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "documents",
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index(op.f("ix_documents_content_sha256"), "documents", ["content_sha256"], unique=False)

    op.add_column("knowledge_chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("chapter", sa.String(length=255), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("subsection", sa.String(length=255), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("domain", sa.String(length=64), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("topic", sa.String(length=64), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("content_type", sa.String(length=32), server_default="text", nullable=False))
    op.add_column("knowledge_chunks", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("language", sa.String(length=8), server_default="sr", nullable=False))
    op.add_column(
        "knowledge_chunks",
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index(op.f("ix_knowledge_chunks_domain"), "knowledge_chunks", ["domain"], unique=False)
    op.create_index(op.f("ix_knowledge_chunks_topic"), "knowledge_chunks", ["topic"], unique=False)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_fts ON knowledge_chunks USING gin (to_tsvector('simple', coalesce(content, '')))"
    )

    op.create_table(
        "knowledge_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("has_text_layer", sa.Boolean(), nullable=False),
        sa.Column("ocr_used", sa.Boolean(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("chapter", sa.String(length=255), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("headings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("image_storage_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_knowledge_pages_document_page"),
    )
    op.create_index(op.f("ix_knowledge_pages_document_id"), "knowledge_pages", ["document_id"], unique=False)

    op.create_table(
        "knowledge_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("chapter", sa.String(length=255), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_assets_document_id"), "knowledge_assets", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_assets_document_id"), table_name="knowledge_assets")
    op.drop_table("knowledge_assets")
    op.drop_index(op.f("ix_knowledge_pages_document_id"), table_name="knowledge_pages")
    op.drop_table("knowledge_pages")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_fts")
    op.drop_index(op.f("ix_knowledge_chunks_topic"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_domain"), table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "extra")
    op.drop_column("knowledge_chunks", "language")
    op.drop_column("knowledge_chunks", "raw_text")
    op.drop_column("knowledge_chunks", "content_type")
    op.drop_column("knowledge_chunks", "topic")
    op.drop_column("knowledge_chunks", "domain")
    op.drop_column("knowledge_chunks", "subsection")
    op.drop_column("knowledge_chunks", "chapter")
    op.drop_column("knowledge_chunks", "page_end")
    op.drop_index(op.f("ix_documents_content_sha256"), table_name="documents")
    op.drop_column("documents", "extra_metadata")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "ocr_version")
    op.drop_column("documents", "parser_version")
    op.drop_column("documents", "language")
    op.drop_column("documents", "source_kind")
    op.drop_column("documents", "content_sha256")
    op.drop_column("documents", "image_count")
    op.drop_column("documents", "page_count")
