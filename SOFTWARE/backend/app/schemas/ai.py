from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import IDSchema
from app.schemas.knowledge import KnowledgeHit


class AIStatusRead(BaseModel):
    provider: str
    chat_model: str
    embedding_model: str
    vision_model: str
    configured: bool


class ConversationCreate(BaseModel):
    title: str | None = None
    parcel_id: UUID | None = None
    disease_case_id: UUID | None = None


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    parcel_id: UUID | None = None


class SourceRef(BaseModel):
    document_id: UUID | None = None
    document_title: str
    page_number: int | None = None
    section_title: str | None = None
    excerpt: str | None = None


class StructuredRef(BaseModel):
    kind: str
    id: UUID | None = None
    label: str
    extra: dict | None = None


class ChatMessageRead(IDSchema):
    role: str
    content: str
    sources: list[dict] | None = None
    structured_refs: list[dict] | None = None
    provider: str | None = None
    model: str | None = None


class ConversationSummary(IDSchema):
    title: str
    farm_id: UUID | None
    parcel_id: UUID | None
    disease_case_id: UUID | None = None
    message_count: int = 0
    last_message_at: datetime | None = None


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessageRead] = Field(default_factory=list)


class DiseaseAnalysisRead(IDSchema):
    farm_id: UUID
    disease_case_id: UUID
    photo_id: UUID | None
    likely_issue: str
    confidence: float
    observed_symptoms: list[str]
    possible_alternatives: list[str]
    recommended_inspection: str
    recommended_next_step: str
    supporting_sources: list[dict]
    observed_facts: str
    uncertainty_notes: str
    disclaimer: str
    provider: str | None
    model: str | None


class DiseaseAnalysisRequest(BaseModel):
    photo_id: UUID | None = None
    notes: str | None = None
