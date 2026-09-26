from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge import KnowledgeAsset, KnowledgeChunk, KnowledgePage


class KnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_farm(self, farm_id: UUID) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.farm_id == farm_id)
            .order_by(Document.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get(self, document_id: UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def get_for_farm(self, document_id: UUID, farm_id: UUID) -> Document | None:
        stmt = select(Document).where(Document.id == document_id, Document.farm_id == farm_id)
        return self.db.scalars(stmt).first()

    def get_by_hash(self, farm_id: UUID, digest: str) -> Document | None:
        stmt = select(Document).where(Document.farm_id == farm_id, Document.content_sha256 == digest)
        return self.db.scalars(stmt).first()

    def add(self, document: Document) -> Document:
        self.db.add(document)
        return document

    def delete(self, document: Document) -> None:
        self.db.delete(document)

    def chunks_for_document(self, document_id: UUID) -> list[KnowledgeChunk]:
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index)
        )
        return list(self.db.scalars(stmt).all())

    def chunks_for_farm(self, farm_id: UUID) -> list[KnowledgeChunk]:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.farm_id == farm_id)
        return list(self.db.scalars(stmt).all())

    def add_chunk(self, chunk: KnowledgeChunk) -> KnowledgeChunk:
        self.db.add(chunk)
        return chunk

    def delete_chunks(self, document_id: UUID) -> None:
        for chunk in self.chunks_for_document(document_id):
            self.db.delete(chunk)

    def get_page(self, document_id: UUID, page_number: int) -> KnowledgePage | None:
        stmt = select(KnowledgePage).where(
            KnowledgePage.document_id == document_id,
            KnowledgePage.page_number == page_number,
        )
        return self.db.scalars(stmt).first()

    def delete_pages(self, document_id: UUID) -> None:
        stmt = select(KnowledgePage).where(KnowledgePage.document_id == document_id)
        for page in self.db.scalars(stmt).all():
            self.db.delete(page)

    def delete_assets(self, document_id: UUID) -> None:
        stmt = select(KnowledgeAsset).where(KnowledgeAsset.document_id == document_id)
        for asset in self.db.scalars(stmt).all():
            self.db.delete(asset)
