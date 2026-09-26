from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ai import AIConversation, AIMessage
from app.models.analysis import DiseaseAnalysis
from app.models.disease import DiseaseCase


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: UUID) -> list[AIConversation]:
        stmt = (
            select(AIConversation)
            .where(AIConversation.user_id == user_id)
            .options(selectinload(AIConversation.messages))
            .order_by(AIConversation.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_for_user(self, conversation_id: UUID, user_id: UUID) -> AIConversation | None:
        stmt = (
            select(AIConversation)
            .where(AIConversation.id == conversation_id, AIConversation.user_id == user_id)
            .options(selectinload(AIConversation.messages))
        )
        return self.db.scalars(stmt).first()

    def add(self, conversation: AIConversation) -> AIConversation:
        self.db.add(conversation)
        return conversation

    def add_message(self, message: AIMessage) -> AIMessage:
        self.db.add(message)
        return message

    def delete(self, conversation: AIConversation) -> None:
        self.db.delete(conversation)


class AnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_case(self, case_id: UUID) -> list[DiseaseAnalysis]:
        stmt = (
            select(DiseaseAnalysis)
            .where(DiseaseAnalysis.disease_case_id == case_id)
            .order_by(DiseaseAnalysis.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_for_parcel(self, owner_id: UUID, parcel_id: UUID) -> list[tuple[DiseaseAnalysis, DiseaseCase]]:
        from app.models.farm import Farm

        stmt = (
            select(DiseaseAnalysis, DiseaseCase)
            .join(DiseaseCase, DiseaseAnalysis.disease_case_id == DiseaseCase.id)
            .join(Farm, DiseaseCase.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id, DiseaseCase.parcel_id == parcel_id)
            .order_by(DiseaseAnalysis.created_at.desc())
        )
        return list(self.db.execute(stmt).all())

    def add(self, analysis: DiseaseAnalysis) -> DiseaseAnalysis:
        self.db.add(analysis)
        return analysis
