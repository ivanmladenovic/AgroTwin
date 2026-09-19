from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus, KnowledgeCategory
from app.schemas.common import IDSchema


class DocumentRead(IDSchema):
    farm_id: UUID
    title: str
    category: KnowledgeCategory
    status: DocumentStatus
    description: str | None
    original_filename: str
    content_type: str
    size_bytes: int | None
    chunk_count: int
    page_count: int = 0
    image_count: int = 0
    source_kind: str = "user"
    language: str = "sr"
    parser_version: str | None = None
    ocr_version: str | None = None
    processed_at: datetime | None = None
    extra_metadata: dict = Field(default_factory=dict)
    error_message: str | None
    uploaded_by_id: UUID | None


class KnowledgeChunkRead(IDSchema):
    document_id: UUID
    document_title: str
    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    token_count: int


class KnowledgeHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    category: KnowledgeCategory
    page_number: int | None = None
    section_title: str | None = None
    content: str
    score: float = 0


class KnowledgeSearchResponse(BaseModel):
    query: str
    hits: list[KnowledgeHit] = Field(default_factory=list)


class RetrievalDebug(BaseModel):
    query: str
    detected_domain: str | None = None
    detected_topic: str | None = None
    searched_documents: list[str] = Field(default_factory=list)
    searched_sections: list[str] = Field(default_factory=list)
    retrieved_chunks: int = 0
    selected_chunks: int = 0
    retrieved_images: int = 0
    confidence: float = 0
    level: int = 0


class EvidenceSource(BaseModel):
    chunk_id: UUID | None = None
    document_id: UUID
    document_title: str
    pages: list[int] = Field(default_factory=list)
    section: str | None = None
    chapter: str | None = None
    content_type: str = "text"
    content: str = ""
    asset_id: UUID | None = None
    storage_key: str | None = None
    score: float = 0


class EvidencePackage(BaseModel):
    query: str
    sufficient_evidence: bool = False
    out_of_scope: bool = False
    commercial: bool = False
    confidence: float = 0
    sources: list[EvidenceSource] = Field(default_factory=list)
    images: list[EvidenceSource] = Field(default_factory=list)
    tables: list[EvidenceSource] = Field(default_factory=list)
    formulas: list[EvidenceSource] = Field(default_factory=list)
    debug: RetrievalDebug | None = None


class AgronomyQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    mode: str = "retrieve"
    include_images: bool = False
    debug: bool = False


class AgronomyQueryResponse(BaseModel):
    question: str
    mode: str
    sufficient_evidence: bool
    out_of_scope: bool = False
    answer: str
    citations: list[str] = Field(default_factory=list)
    evidence: EvidencePackage
    debug: RetrievalDebug | None = None
