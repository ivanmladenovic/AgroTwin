from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.ai import (
    AIStatusRead,
    ChatMessageCreate,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    DiseaseAnalysisRead,
    DiseaseAnalysisRequest,
)
from app.services.agronomist import AgronomistService
from app.services.agronomy_query import AgronomyQueryService
from app.services.analysis import AnalysisService
from app.schemas.knowledge import AgronomyQueryRequest, AgronomyQueryResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=AIStatusRead)
def ai_status(db: DBSession) -> AIStatusRead:
    return AIStatusRead.model_validate(AgronomistService(db).status())


@router.post("/agronomy/query", response_model=AgronomyQueryResponse)
def agronomy_query(
    payload: AgronomyQueryRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> AgronomyQueryResponse:
    return AgronomyQueryService(db).query(
        current_user.id,
        payload.question,
        mode=payload.mode,
        include_images=payload.include_images,
        debug=payload.debug,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(current_user: CurrentUser, db: DBSession) -> list[ConversationSummary]:
    return AgronomistService(db).list_conversations(current_user.id)


@router.post("/conversations", response_model=ConversationDetail, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> ConversationDetail:
    service = AgronomistService(db)
    item = service.create_conversation(current_user.id, payload.title, payload.parcel_id)
    return service.to_detail(service.get_conversation(item.id, current_user.id))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ConversationDetail:
    service = AgronomistService(db)
    return service.to_detail(service.get_conversation(conversation_id, current_user.id))


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    AgronomistService(db).delete_conversation(conversation_id, current_user.id)


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationDetail)
def send_message(
    conversation_id: UUID,
    payload: ChatMessageCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> ConversationDetail:
    service = AgronomistService(db)
    conversation = service.ask(
        conversation_id,
        current_user.id,
        payload.content,
        payload.parcel_id,
    )
    return service.to_detail(conversation)


@router.get("/disease-cases/{case_id}/analyses", response_model=list[DiseaseAnalysisRead])
def list_analyses(case_id: UUID, current_user: CurrentUser, db: DBSession) -> list[DiseaseAnalysisRead]:
    return AnalysisService(db).list_for_case(case_id, current_user.id)


@router.post("/disease-cases/{case_id}/analyses", response_model=DiseaseAnalysisRead, status_code=201)
def request_analysis(
    case_id: UUID,
    payload: DiseaseAnalysisRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> DiseaseAnalysisRead:
    service = AnalysisService(db)
    item = service.analyze(case_id, current_user.id, photo_id=payload.photo_id, notes=payload.notes)
    return service.to_read(item)
