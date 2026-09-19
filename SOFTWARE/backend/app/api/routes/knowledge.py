from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import CurrentUser, DBSession
from app.models.enums import KnowledgeCategory
from app.schemas.knowledge import DocumentRead, KnowledgeChunkRead, KnowledgeSearchResponse
from app.services.knowledge import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(current_user: CurrentUser, db: DBSession) -> list[DocumentRead]:
    return KnowledgeService(db).list_documents(current_user.id)


@router.post("/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    category: KnowledgeCategory = Form(default=KnowledgeCategory.OTHER),
    description: str | None = Form(default=None),
) -> DocumentRead:
    content = await file.read()
    service = KnowledgeService(db)
    document = service.create_and_ingest(
        current_user.id,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "application/pdf",
        content=content,
        title=title,
        category=category,
        description=description,
        uploaded_by_id=current_user.id,
    )
    return service.to_document_read(document)


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: UUID, current_user: CurrentUser, db: DBSession) -> DocumentRead:
    service = KnowledgeService(db)
    return service.to_document_read(service.get_document(document_id, current_user.id))


@router.get("/documents/{document_id}/chunks", response_model=list[KnowledgeChunkRead])
def list_chunks(document_id: UUID, current_user: CurrentUser, db: DBSession) -> list[KnowledgeChunkRead]:
    return KnowledgeService(db).list_chunks(document_id, current_user.id)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    KnowledgeService(db).delete_document(document_id, current_user.id)


@router.get("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(current_user: CurrentUser, db: DBSession, q: str, limit: int = 6) -> KnowledgeSearchResponse:
    hits = KnowledgeService(db).search(current_user.id, q, limit=min(limit, 20))
    return KnowledgeSearchResponse(query=q, hits=hits)
