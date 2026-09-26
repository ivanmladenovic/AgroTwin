from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.core.exceptions import AppError, NotFoundError
from app.knowledge.chunking import chunk_structured_pages
from app.knowledge.ocr import PARSER_VERSION, sha256_bytes, tesseract_version
from app.knowledge.parse import ParsedPage, parse_pdf_pages
from app.knowledge.structure import assign_structure
from app.knowledge.taxonomy import CROP, PUBLISHER, match_manual
from app.models.document import Document
from app.models.enums import AttachmentEntityType, DocumentStatus, KnowledgeCategory
from app.models.farm import Farm
from app.models.knowledge import KnowledgeAsset, KnowledgeChunk, KnowledgePage
from app.repositories.farm import FarmRepository
from app.repositories.knowledge import KnowledgeRepository
from app.schemas.knowledge import DocumentRead, KnowledgeChunkRead, KnowledgeHit
from app.storage import get_storage

MAX_PDF_BYTES = 50 * 1024 * 1024


class KnowledgeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.docs = KnowledgeRepository(db)
        self.farms = FarmRepository(db)
        self.storage = get_storage()
        self.provider = get_ai_provider()

    def list_documents(self, owner_id: UUID) -> list[DocumentRead]:
        farm = self._farm(owner_id)
        return [self.to_document_read(item) for item in self.docs.list_for_farm(farm.id)]

    def get_document(self, document_id: UUID, owner_id: UUID) -> Document:
        farm = self._farm(owner_id)
        document = self.docs.get_for_farm(document_id, farm.id)
        if document is None:
            raise NotFoundError("Dokument nije pronađen")
        return document

    def create_and_ingest(
        self,
        owner_id: UUID,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        title: str | None,
        category: KnowledgeCategory,
        description: str | None,
        uploaded_by_id: UUID,
        source_kind: str = "user",
    ) -> Document:
        if content_type not in {"application/pdf", "application/x-pdf"} and not filename.lower().endswith(".pdf"):
            raise AppError("U ovoj verziji se prihvataju samo PDF datoteke", status_code=422, code="invalid_document")
        if len(content) > MAX_PDF_BYTES:
            raise AppError("PDF je veći od 50 MB", status_code=422, code="document_too_large")
        farm = self._farm(owner_id)
        key = f"documents/{farm.id}/{uuid4().hex}.pdf"
        self.storage.put(key, content, "application/pdf")
        document = Document(
            farm_id=farm.id,
            entity_type=AttachmentEntityType.FARM,
            entity_id=farm.id,
            title=(title or filename).strip() or filename,
            category=category,
            status=DocumentStatus.PROCESSING,
            description=description,
            storage_key=key,
            original_filename=filename,
            content_type="application/pdf",
            size_bytes=len(content),
            uploaded_by_id=uploaded_by_id,
            source_kind=source_kind,
            content_sha256=sha256_bytes(content),
        )
        self.docs.add(document)
        self.db.flush()
        try:
            self._ingest(document, content)
            document.status = DocumentStatus.READY
            document.error_message = None
        except Exception as exc:  # noqa: BLE001
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)[:1000]
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete_document(self, document_id: UUID, owner_id: UUID) -> None:
        document = self.get_document(document_id, owner_id)
        for asset in list(document.assets):
            self.storage.delete(asset.storage_key)
        for page in list(document.pages):
            if page.image_storage_key:
                self.storage.delete(page.image_storage_key)
        self.storage.delete(document.storage_key)
        self.docs.delete(document)
        self.db.commit()

    def file_local_path(self, document: Document) -> Path | None:
        return self.storage.local_path(document.storage_key)

    def file_bytes(self, document: Document) -> tuple[bytes, str]:
        return self.storage.get(document.storage_key), document.content_type or "application/pdf"

    def page_bytes(self, document: Document, page_number: int) -> tuple[bytes, str]:
        if page_number < 1:
            raise NotFoundError("Strana nije pronađena")
        if document.page_count and page_number > document.page_count:
            raise NotFoundError("Strana nije pronađena")
        page = self.docs.get_page(document.id, page_number)
        if page and page.image_storage_key:
            return self.storage.get(page.image_storage_key), "image/jpeg"
        return self._render_page(document, page_number), "image/jpeg"

    def page_local_path(self, document: Document, page_number: int):
        page = self.docs.get_page(document.id, page_number)
        if page and page.image_storage_key:
            return self.storage.local_path(page.image_storage_key)
        return None

    def _render_page(self, document: Document, page_number: int) -> bytes:
        try:
            import fitz
        except ImportError as exc:
            raise AppError("PDF stranica nije dostupna", status_code=500, code="pdf_render") from exc
        content = self.storage.get(document.storage_key)
        pdf = fitz.open(stream=content, filetype="pdf")
        try:
            if page_number > pdf.page_count:
                raise NotFoundError("Strana nije pronađena")
            pixmap = pdf[page_number - 1].get_pixmap(matrix=fitz.Matrix(160 / 72, 160 / 72), alpha=False)
            return pixmap.tobytes("jpeg")
        finally:
            pdf.close()

    def list_chunks(self, document_id: UUID, owner_id: UUID) -> list[KnowledgeChunkRead]:
        document = self.get_document(document_id, owner_id)
        return [self.to_chunk_read(item, document) for item in self.docs.chunks_for_document(document.id)]

    def search(self, owner_id: UUID, query: str, limit: int = 6) -> list[KnowledgeHit]:
        farm = self._farm(owner_id)
        return self.search_farm(farm.id, query, limit=limit)

    def search_farm(self, farm_id: UUID, query: str, limit: int = 6) -> list[KnowledgeHit]:
        if not query.strip():
            return []
        vector = self.provider.generate_embedding(query)
        hits = self._search_pgvector(farm_id, vector, limit) if vector else []
        if not hits:
            hits = self._search_python(farm_id, vector, limit)
        return hits

    def ingest_or_skip(
        self,
        owner_id: UUID,
        *,
        filename: str,
        content: bytes,
        title: str,
        category: KnowledgeCategory,
        uploaded_by_id: UUID,
        source_kind: str = "agriser_manual",
        force: bool = False,
    ) -> Document:
        farm = self._farm(owner_id)
        digest = sha256_bytes(content)
        existing = self.docs.get_by_hash(farm.id, digest)
        if existing is not None and existing.status == DocumentStatus.READY and not force:
            return existing
        if existing is not None:
            self.storage.delete(existing.storage_key)
            self.docs.delete(existing)
            self.db.flush()
        return self.create_and_ingest(
            owner_id,
            filename=filename,
            content_type="application/pdf",
            content=content,
            title=title,
            category=category,
            description=None,
            uploaded_by_id=uploaded_by_id,
            source_kind=source_kind,
        )

    def reindex_agriser(self, owner_id: UUID) -> list[Document]:
        farm = self._farm(owner_id)
        documents = [
            item
            for item in self.docs.list_for_farm(farm.id)
            if item.source_kind == "agriser_manual" and item.status == DocumentStatus.READY
        ]
        for document in documents:
            self._reindex_from_pages(document)
        self.db.commit()
        for document in documents:
            self.db.refresh(document)
        return documents

    def _reindex_from_pages(self, document: Document) -> None:
        page_rows = sorted(document.pages, key=lambda item: item.page_number)
        if not page_rows:
            raise AppError("Dokument nema sačuvane stranice za reindeksiranje", status_code=422, code="empty_pdf")
        parsed = [
            ParsedPage(
                page_number=row.page_number,
                raw_text=row.raw_text or "",
                has_text_layer=row.has_text_layer,
                ocr_used=row.ocr_used,
                image_png=b"x" if row.image_storage_key else None,
                embedded_images=[],
            )
            for row in page_rows
        ]
        manual = match_manual(document.original_filename, document.title)
        structured = assign_structure(parsed, manual)
        for row, page in zip(page_rows, structured, strict=True):
            row.chapter = page.chapter
            row.section = page.section
            row.headings = page.headings
            row.normalized_text = page.normalized_text
        for asset in document.assets:
            match = next((item for item in structured if item.page_number == asset.page_number), None)
            if match is None:
                continue
            asset.chapter = match.chapter
            asset.section = match.section
            asset.context = (match.normalized_text or "")[:800]
        self._replace_chunks(document, structured)

    def _replace_chunks(self, document: Document, structured: list) -> None:
        self.docs.delete_chunks(document.id)
        pieces = chunk_structured_pages(structured, document.title)
        if not pieces:
            raise AppError("Tekst iz ovog PDF-a nije mogao da se izvuče", status_code=422, code="empty_pdf")
        embeddings = self.provider.generate_embeddings([str(item["content"]) for item in pieces])
        for piece, embedding in zip(pieces, embeddings, strict=True):
            chunk = KnowledgeChunk(
                document_id=document.id,
                farm_id=document.farm_id,
                chunk_index=int(piece["chunk_index"]),
                page_number=piece.get("page_number"),  # type: ignore[arg-type]
                page_end=piece.get("page_end"),  # type: ignore[arg-type]
                section_title=piece.get("section_title"),  # type: ignore[arg-type]
                chapter=piece.get("chapter"),  # type: ignore[arg-type]
                subsection=piece.get("subsection"),  # type: ignore[arg-type]
                domain=piece.get("domain"),  # type: ignore[arg-type]
                topic=piece.get("topic"),  # type: ignore[arg-type]
                content_type=str(piece.get("content_type") or "text"),
                raw_text=str(piece.get("raw_text") or piece["content"]),
                language=str(piece.get("language") or "sr"),
                extra=piece.get("extra") or {},
                content=str(piece["content"]),
                token_count=int(piece["token_count"]),
                embedding=embedding,
                embedding_model=self.provider.embedding_model,
            )
            self.docs.add_chunk(chunk)
            if embedding and self._has_pgvector():
                self.db.flush()
                try:
                    with self.db.begin_nested():
                        self.db.execute(
                            text(
                                "UPDATE knowledge_chunks SET embedding_vec = CAST(:vec AS vector) WHERE id = CAST(:id AS uuid)"
                            ),
                            {"vec": _to_vector_literal(embedding), "id": str(chunk.id)},
                        )
                except Exception:
                    pass
        document.chunk_count = len(pieces)
        document.parser_version = PARSER_VERSION
        document.processed_at = datetime.now(timezone.utc)
        self.db.flush()

    def _ingest(self, document: Document, content: bytes) -> None:
        self.docs.delete_chunks(document.id)
        self.docs.delete_pages(document.id)
        self.docs.delete_assets(document.id)
        document.content_sha256 = sha256_bytes(content)
        parsed = parse_pdf_pages(content)
        manual = match_manual(document.original_filename, document.title)
        structured = assign_structure(parsed, manual)
        if not any((page.normalized_text or "").strip() for page in structured):
            raise AppError("Tekst iz ovog PDF-a nije mogao da se izvuče", status_code=422, code="empty_pdf")
        if manual:
            document.title = manual.title
            document.category = KnowledgeCategory(manual.category)
            document.source_kind = "agriser_manual"
            document.language = "sr"
            document.extra_metadata = {
                "publisher": PUBLISHER,
                "crop": CROP,
                "language": "sr",
                "document_type": "agronomy_manual",
                "domain": manual.domain,
                "sections": list(manual.sections),
            }
        image_count = 0
        for page in structured:
            image_key = None
            if page.image_png:
                image_key = f"knowledge/{document.farm_id}/{document.id}/pages/{page.page_number}.jpg"
                self.storage.put(image_key, _to_jpeg(page.image_png), "image/jpeg")
                image_count += 1
                self.db.add(
                    KnowledgeAsset(
                        document_id=document.id,
                        page_number=page.page_number,
                        asset_type="page",
                        storage_key=image_key,
                        caption=None,
                        context=(page.normalized_text or "")[:800],
                        chapter=page.chapter,
                        section=page.section,
                        extra={"ocr_used": page.ocr_used},
                    )
                )
            for index, blob in enumerate(page.embedded_images, start=1):
                if page.image_png and blob == page.image_png:
                    continue
                key = f"knowledge/{document.farm_id}/{document.id}/images/{page.page_number}-{index}.bin"
                self.storage.put(key, blob, "application/octet-stream")
                image_count += 1
                self.db.add(
                    KnowledgeAsset(
                        document_id=document.id,
                        page_number=page.page_number,
                        asset_type="figure",
                        storage_key=key,
                        context=(page.normalized_text or "")[:800],
                        chapter=page.chapter,
                        section=page.section,
                        extra={},
                    )
                )
            self.db.add(
                KnowledgePage(
                    document_id=document.id,
                    page_number=page.page_number,
                    has_text_layer=page.has_text_layer,
                    ocr_used=page.ocr_used,
                    raw_text=page.raw_text,
                    normalized_text=page.normalized_text,
                    chapter=page.chapter,
                    section=page.section,
                    headings=page.headings,
                    image_storage_key=image_key,
                )
            )
        document.page_count = len(structured)
        document.image_count = image_count
        document.ocr_version = tesseract_version() or None
        self._replace_chunks(document, structured)

    def _search_pgvector(self, farm_id: UUID, vector: list[float], limit: int) -> list[KnowledgeHit]:
        if not self._has_pgvector():
            return []
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT c.id, 1 - (c.embedding_vec <=> CAST(:vec AS vector)) AS score
                    FROM knowledge_chunks c
                    WHERE c.farm_id = CAST(:farm_id AS uuid) AND c.embedding_vec IS NOT NULL
                    ORDER BY c.embedding_vec <=> CAST(:vec AS vector)
                    LIMIT :limit
                    """
                ),
                {"vec": _to_vector_literal(vector), "farm_id": str(farm_id), "limit": limit},
            ).all()
        except Exception:
            self.db.rollback()
            return []
        hits: list[KnowledgeHit] = []
        for chunk_id, score in rows:
            chunk = self.db.get(KnowledgeChunk, chunk_id)
            if chunk is None:
                continue
            document = self.db.get(Document, chunk.document_id)
            if document is None:
                continue
            hits.append(self.to_hit(chunk, document, float(score or 0)))
        return hits

    def _search_python(self, farm_id: UUID, vector: list[float], limit: int) -> list[KnowledgeHit]:
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in self.docs.chunks_for_farm(farm_id):
            if not chunk.embedding:
                continue
            scored.append((_cosine(vector, chunk.embedding), chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits: list[KnowledgeHit] = []
        for score, chunk in scored[:limit]:
            document = self.db.get(Document, chunk.document_id)
            if document is None:
                continue
            hits.append(self.to_hit(chunk, document, score))
        return hits

    def _has_pgvector(self) -> bool:
        try:
            return bool(self.db.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")))
        except Exception:
            return False

    def _farm(self, owner_id: UUID) -> Farm:
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]

    def to_document_read(self, document: Document) -> DocumentRead:
        return DocumentRead(
            id=document.id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            farm_id=document.farm_id,
            title=document.title,
            category=document.category,
            status=document.status,
            description=document.description,
            original_filename=document.original_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            chunk_count=document.chunk_count,
            page_count=document.page_count,
            image_count=document.image_count,
            source_kind=document.source_kind,
            language=document.language,
            parser_version=document.parser_version,
            ocr_version=document.ocr_version,
            processed_at=document.processed_at,
            extra_metadata=document.extra_metadata or {},
            error_message=document.error_message,
            uploaded_by_id=document.uploaded_by_id,
        )

    def to_chunk_read(self, chunk: KnowledgeChunk, document: Document) -> KnowledgeChunkRead:
        return KnowledgeChunkRead(
            id=chunk.id,
            created_at=chunk.created_at,
            updated_at=chunk.updated_at,
            document_id=chunk.document_id,
            document_title=document.title,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            content=chunk.content,
            token_count=chunk.token_count,
        )

    def to_hit(self, chunk: KnowledgeChunk, document: Document, score: float) -> KnowledgeHit:
        return KnowledgeHit(
            chunk_id=chunk.id,
            document_id=document.id,
            document_title=document.title,
            category=document.category,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            content=chunk.content,
            score=round(score, 4),
        )


def _cosine(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    if length == 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(length))
    n1 = math.sqrt(sum(value * value for value in left[:length])) or 1.0
    n2 = math.sqrt(sum(value * value for value in right[:length])) or 1.0
    return dot / (n1 * n2)


def _to_vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _to_jpeg(png_bytes: bytes) -> bytes:
    try:
        from io import BytesIO
        from PIL import Image

        image = Image.open(BytesIO(png_bytes)).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=72, optimize=True)
        return buffer.getvalue()
    except Exception:
        return png_bytes
