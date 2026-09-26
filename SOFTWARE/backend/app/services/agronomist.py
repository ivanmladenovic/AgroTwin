from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.base import ChatMessage
from app.ai.prompts import SYSTEM_PROMPT
from app.core.exceptions import NotFoundError
from app.models.ai import AIConversation, AIMessage
from app.models.enums import AIMessageRole
from app.repositories.ai import ConversationRepository
from app.repositories.farm import FarmRepository
from app.schemas.ai import ChatMessageRead, ConversationDetail, ConversationSummary
from app.services.farm_context import TOOL_SPECS, FarmContextService
from app.services.knowledge import KnowledgeService


class AgronomistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.farms = FarmRepository(db)
        self.context = FarmContextService(db)
        self.knowledge = KnowledgeService(db)
        self.provider = get_ai_provider()

    def status(self) -> dict:
        return {
            "provider": self.provider.name,
            "chat_model": self.provider.chat_model,
            "embedding_model": self.provider.embedding_model,
            "vision_model": self.provider.vision_model,
            "configured": True,
        }

    def list_conversations(self, owner_id: UUID) -> list[ConversationSummary]:
        return [self.to_summary(item) for item in self.conversations.list_for_user(owner_id)]

    def get_conversation(self, conversation_id: UUID, owner_id: UUID) -> AIConversation:
        item = self.conversations.get_for_user(conversation_id, owner_id)
        if item is None:
            raise NotFoundError("Razgovor nije pronađen")
        return item

    def create_conversation(
        self,
        owner_id: UUID,
        title: str | None,
        parcel_id: UUID | None,
        disease_case_id: UUID | None = None,
    ) -> AIConversation:
        farms = self.farms.list_by_owner(owner_id)
        farm_id = farms[0].id if farms else None
        if disease_case_id is not None:
            from app.services.disease import DiseaseService

            case = DiseaseService(self.db).get_case(disease_case_id, owner_id)
            parcel_id = parcel_id or case.parcel_id
            title = title or case.title
        conversation = AIConversation(
            user_id=owner_id,
            farm_id=farm_id,
            parcel_id=parcel_id,
            disease_case_id=disease_case_id,
            title=(title or "Pitanje o voćnjaku").strip()[:255],
        )
        self.conversations.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def delete_conversation(self, conversation_id: UUID, owner_id: UUID) -> None:
        conversation = self.get_conversation(conversation_id, owner_id)
        self.conversations.delete(conversation)
        self.db.commit()

    def ask(self, conversation_id: UUID, owner_id: UUID, content: str, parcel_id: UUID | None) -> AIConversation:
        conversation = self.get_conversation(conversation_id, owner_id)
        if parcel_id:
            conversation.parcel_id = parcel_id
        if conversation.title in {"Orchard question", "Pitanje o voćnjaku"}:
            conversation.title = content.strip()[:80]
        user_message = AIMessage(
            conversation_id=conversation.id,
            role=AIMessageRole.USER.value,
            content=content.strip(),
        )
        self.conversations.add_message(user_message)
        self.db.flush()

        from app.ai.prompts import AGRONOMY_SYSTEM_PROMPT, format_evidence_block
        from app.knowledge.retrieve import retrieve_evidence
        from app.knowledge.taxonomy import INSUFFICIENT_EVIDENCE_MESSAGE, OUT_OF_SCOPE_MESSAGE, classify_query
        from app.models.enums import DocumentStatus

        farm = self.farms.list_by_owner(owner_id)
        route = classify_query(content)
        evidence = None
        if farm:
            agriser_ready = any(
                item.source_kind == "agriser_manual" and item.status == DocumentStatus.READY
                for item in self.knowledge.docs.list_for_farm(farm[0].id)
            )
            closed = agriser_ready and (
                route.out_of_scope or route.commercial or bool(route.document_keys) or bool(route.domains)
            )
            if closed:
                evidence = retrieve_evidence(self.db, farm[0].id, content, agriser_only=True)
        if evidence is not None:
            sources = [
                {
                    "document_id": str(item.document_id),
                    "document_title": item.document_title,
                    "page_number": item.pages[0] if item.pages else None,
                    "section_title": item.section,
                    "excerpt": item.content[:280],
                }
                for item in evidence.sources[:6]
            ]
            if evidence.out_of_scope:
                answer_text = OUT_OF_SCOPE_MESSAGE
                knowledge_block = format_evidence_block(evidence)
            elif not evidence.sufficient_evidence:
                answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
                knowledge_block = format_evidence_block(evidence)
            else:
                answer_text = None
                knowledge_block = format_evidence_block(evidence)
            system_prompt = AGRONOMY_SYSTEM_PROMPT
        else:
            hits = self.knowledge.search(owner_id, content, limit=6)
            answer_text = None
            system_prompt = SYSTEM_PROMPT
            sources = [
                {
                    "document_id": str(item.document_id),
                    "document_title": item.document_title,
                    "page_number": item.page_number,
                    "section_title": item.section_title,
                    "excerpt": item.content[:280],
                }
                for item in hits
            ]
            knowledge_block = "Knowledge excerpts:\n" + "\n".join(
                f"SOURCE: {item.document_title}\nPAGE: {item.page_number or '-'}\nTEXT: {item.content[:500]}"
                for item in hits
            )
            if not hits:
                knowledge_block = "Knowledge excerpts:\nNema. Recite ako priručnici ne pokrivaju ovo pitanje."

        history = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="system", content=knowledge_block),
        ]
        case_block, photo_parts = self._problem_context(
            conversation,
            owner_id,
            first_turn=not any(
                item.role == AIMessageRole.USER.value and item.id != user_message.id for item in conversation.messages
            ),
        )
        if case_block:
            history.append(ChatMessage(role="system", content=case_block))
        for message in conversation.messages:
            if message.id == user_message.id:
                continue
            if message.role in {AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value}:
                history.append(ChatMessage(role=message.role, content=message.content))
        user_content: str | list = content.strip()
        if photo_parts:
            user_content = [{"type": "text", "text": content.strip()}, *photo_parts]
        history.append(ChatMessage(role="user", content=user_content))

        structured_refs: list[dict] = []
        if answer_text:
            result_content = answer_text
            result_model = self.provider.chat_model
        else:
            chat_tools = None if evidence is not None else TOOL_SPECS
            result = self.provider.chat(history, tools=chat_tools)
            rounds = 0
            while result.tool_calls and rounds < 4:
                rounds += 1
                history.append(
                    ChatMessage(role="assistant", content=result.content or "", tool_calls=result.tool_calls)
                )
                for call in result.tool_calls:
                    payload = self.context.dispatch(owner_id, call.name, call.arguments)
                    structured_refs.append(
                        {
                            "kind": call.name,
                            "id": payload.get("id"),
                            "label": call.name,
                            "extra": {key: value for key, value in payload.items() if key != "id"},
                        }
                    )
                    history.append(
                        ChatMessage(
                            role="tool",
                            content=json.dumps(payload, default=str),
                            tool_call_id=call.id,
                        )
                    )
                result = self.provider.chat(history, tools=TOOL_SPECS)
            result_content = (result.content or "").strip()
            result_model = result.model
        answer = result_content or "I could not form an answer from the current records and manuals."
        assistant = AIMessage(
            conversation_id=conversation.id,
            role=AIMessageRole.ASSISTANT.value,
            content=answer,
            sources=sources or None,
            structured_refs=structured_refs or None,
            provider=self.provider.name,
            model=result_model,
        )
        self.conversations.add_message(assistant)
        self.db.commit()
        self.db.expire_all()
        loaded = self.conversations.get_for_user(conversation.id, owner_id)
        assert loaded is not None
        return loaded

    def _problem_context(
        self,
        conversation: AIConversation,
        owner_id: UUID,
        *,
        first_turn: bool,
    ) -> tuple[str | None, list[dict]]:
        if conversation.disease_case_id is None:
            return None, []
        import base64

        from app.services.disease import DiseaseService

        diseases = DiseaseService(self.db)
        detail = diseases.get_case_detail(conversation.disease_case_id, owner_id)
        location = detail.tree_public_id or (
            f"Red {detail.row_number}" if detail.row_number is not None else detail.parcel_name or "parcela"
        )
        symptoms = next((item.symptoms for item in detail.observations if item.symptoms), None)
        lines = [
            "PRIJAVLJENI PROBLEM IZ EVIDENCIJE:",
            f"Naslov: {detail.title}",
            f"Parcela: {detail.parcel_name or '-'}",
            f"Lokacija: {location}",
            f"Kategorija: {detail.category.value}",
            f"Ozbiljnost: {detail.severity.value}",
            f"Datum: {detail.detected_on}",
            f"Opis: {detail.description or '-'}",
            f"Simptomi: {symptoms or '-'}",
            f"Beleške: {detail.notes or '-'}",
            f"Broj fotografija: {detail.photo_count}",
            "Odgovorite u razgovoru sa proizvođačem. Ovo nije potvrđena dijagnoza.",
        ]
        photo_parts: list[dict] = []
        if first_turn:
            for photo in detail.photos[:3]:
                stored = diseases.get_photo(photo.id, owner_id)
                image, mime = diseases.photo_bytes(stored)
                encoded = base64.b64encode(image).decode("ascii")
                photo_parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
                )
        return "\n".join(lines), photo_parts

    def to_summary(self, conversation: AIConversation) -> ConversationSummary:
        messages = list(conversation.messages or [])
        last = messages[-1] if messages else None
        return ConversationSummary(
            id=conversation.id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            title=conversation.title,
            farm_id=conversation.farm_id,
            parcel_id=conversation.parcel_id,
            disease_case_id=conversation.disease_case_id,
            message_count=len(messages),
            last_message_at=last.created_at if last else conversation.updated_at,
        )

    def to_detail(self, conversation: AIConversation) -> ConversationDetail:
        summary = self.to_summary(conversation)
        return ConversationDetail(
            **summary.model_dump(),
            messages=[self.to_message_read(item) for item in sorted(conversation.messages, key=lambda item: item.created_at)],
        )

    def to_message_read(self, message: AIMessage) -> ChatMessageRead:
        return ChatMessageRead(
            id=message.id,
            created_at=message.created_at,
            updated_at=message.updated_at,
            role=message.role,
            content=message.content,
            sources=message.sources,
            structured_refs=message.structured_refs,
            provider=message.provider,
            model=message.model,
        )
