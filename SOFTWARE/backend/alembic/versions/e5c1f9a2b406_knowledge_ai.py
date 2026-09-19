"""knowledge base, chunks and AI conversations

Revision ID: e5c1f9a2b406
Revises: d4b8e2c1a305
Create Date: 2026-09-14 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5c1f9a2b406"
down_revision: Union[str, Sequence[str], None] = "d4b8e2c1a305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception:
            pass

    knowledge_category = postgresql.ENUM(
        "manual",
        "disease_guide",
        "pest_guide",
        "nutrition_guide",
        "plant_protection",
        "best_practice",
        "other",
        name="knowledge_category",
    )
    knowledge_category.create(bind, checkfirst=True)
    document_status = postgresql.ENUM(
        "pending",
        "processing",
        "ready",
        "failed",
        name="document_status",
    )
    document_status.create(bind, checkfirst=True)

    op.add_column("documents", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "category",
            postgresql.ENUM(
                "manual",
                "disease_guide",
                "pest_guide",
                "nutrition_guide",
                "plant_protection",
                "best_practice",
                "other",
                name="knowledge_category",
                create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "ready",
                "failed",
                name="document_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("documents", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("storage_key", sa.String(length=512), nullable=True))
    op.add_column("documents", sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.execute("UPDATE documents SET storage_key = storage_path WHERE storage_key IS NULL")
    op.execute("UPDATE documents SET title = original_filename WHERE title IS NULL")
    op.alter_column("documents", "storage_key", existing_type=sa.String(length=512), nullable=False)
    op.alter_column("documents", "title", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("documents", "storage_path")
    op.create_index(op.f("ix_documents_category"), "documents", ["category"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    op.add_column("ai_conversations", sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_ai_conversations_parcel_id"), "ai_conversations", ["parcel_id"], unique=False)
    op.create_foreign_key(
        "fk_ai_conversations_parcel_id",
        "ai_conversations",
        "parcels",
        ["parcel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("ai_messages", sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("ai_messages", sa.Column("structured_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("ai_messages", sa.Column("provider", sa.String(length=64), nullable=True))
    op.add_column("ai_messages", sa.Column("model", sa.String(length=128), nullable=True))

    op.create_table(
        "knowledge_chunks",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_chunks_document_id"), "knowledge_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_knowledge_chunks_farm_id"), "knowledge_chunks", ["farm_id"], unique=False)

    op.create_table(
        "disease_analyses",
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("disease_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("likely_issue", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("observed_symptoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("possible_alternatives", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_inspection", sa.Text(), nullable=False),
        sa.Column("recommended_next_step", sa.Text(), nullable=False),
        sa.Column("supporting_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_facts", sa.Text(), nullable=False),
        sa.Column("uncertainty_notes", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["disease_case_id"], ["disease_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_disease_analyses_disease_case_id"), "disease_analyses", ["disease_case_id"], unique=False)
    op.create_index(op.f("ix_disease_analyses_farm_id"), "disease_analyses", ["farm_id"], unique=False)

    has_vector = bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
    if has_vector:
        op.execute("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)")


def downgrade() -> None:
    bind = op.get_bind()
    has_vector = bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
    if has_vector:
        op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding_vec")
    op.drop_index(op.f("ix_disease_analyses_farm_id"), table_name="disease_analyses")
    op.drop_index(op.f("ix_disease_analyses_disease_case_id"), table_name="disease_analyses")
    op.drop_table("disease_analyses")
    op.drop_index(op.f("ix_knowledge_chunks_farm_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_column("ai_messages", "model")
    op.drop_column("ai_messages", "provider")
    op.drop_column("ai_messages", "structured_refs")
    op.drop_column("ai_messages", "sources")
    op.drop_constraint("fk_ai_conversations_parcel_id", "ai_conversations", type_="foreignkey")
    op.drop_index(op.f("ix_ai_conversations_parcel_id"), table_name="ai_conversations")
    op.drop_column("ai_conversations", "parcel_id")
    op.add_column("documents", sa.Column("storage_path", sa.String(length=512), nullable=True))
    op.execute("UPDATE documents SET storage_path = storage_key")
    op.alter_column("documents", "storage_path", existing_type=sa.String(length=512), nullable=False)
    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_category"), table_name="documents")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "description")
    op.drop_column("documents", "status")
    op.drop_column("documents", "category")
    op.drop_column("documents", "title")
    postgresql.ENUM(name="document_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="knowledge_category").drop(bind, checkfirst=True)
