from __future__ import annotations

import base64
import json
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.base import ChatMessage
from app.ai.prompts import SYSTEM_PROMPT
from app.core.exceptions import AppError, NotFoundError
from app.models.ai import AIConversation, AIMessage
from app.models.enums import AIMessageRole
from app.repositories.ai import ConversationRepository
from app.repositories.farm import FarmRepository
from app.schemas.ai import ChatMessageRead, ConversationDetail, ConversationSummary
from app.services.farm_context import TOOL_SPECS, FarmContextService
from app.services.knowledge import KnowledgeService
from app.storage import get_storage
from app.storage.images import compress_photo

ALLOWED_CHAT_PHOTO_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
# Client converts HEIC→PNG and downscales first; keep headroom for large phone photos.
MAX_CHAT_PHOTO_BYTES = 25 * 1024 * 1024
CHAT_PHOTO_PLACEHOLDER = "Pogledajte priloženu fotografiju."


class AgronomistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.farms = FarmRepository(db)
        self.context = FarmContextService(db)
        self.knowledge = KnowledgeService(db)
        self.provider = get_ai_provider()
        self.storage = get_storage()

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
        image_keys: list[str] = []
        for message in conversation.messages or []:
            for ref in message.structured_refs or []:
                if ref.get("kind") != "chat_image":
                    continue
                key = (ref.get("extra") or {}).get("storage_key")
                if isinstance(key, str) and key:
                    image_keys.append(key)
        self.conversations.delete(conversation)
        self.db.commit()
        for key in image_keys:
            try:
                self.storage.delete(key)
            except Exception:
                pass

    def ask(
        self,
        conversation_id: UUID,
        owner_id: UUID,
        content: str,
        parcel_id: UUID | None,
        *,
        image: bytes | None = None,
        image_filename: str | None = None,
        image_content_type: str | None = None,
    ) -> AIConversation:
        conversation = self.get_conversation(conversation_id, owner_id)
        if parcel_id:
            conversation.parcel_id = parcel_id

        text = (content or "").strip()
        chat_photo_ref: dict | None = None
        chat_photo_parts: list[dict] = []
        if image is not None:
            chat_photo_ref, chat_photo_parts = self._store_chat_photo(
                conversation,
                image=image,
                filename=image_filename or "photo.jpg",
                content_type=image_content_type,
            )
            if not text:
                text = CHAT_PHOTO_PLACEHOLDER

        if not text:
            raise AppError("Poruka ne sme biti prazna", status_code=422, code="empty_message")

        if conversation.title in {"Orchard question", "Pitanje o voćnjaku"}:
            conversation.title = text[:80]
        user_message = AIMessage(
            conversation_id=conversation.id,
            role=AIMessageRole.USER.value,
            content=text,
            structured_refs=[chat_photo_ref] if chat_photo_ref else None,
        )
        self.conversations.add_message(user_message)
        self.db.flush()

        from app.ai.prompts import (
            ADVICE_SYSTEM_PROMPT,
            AGRONOMY_SYSTEM_PROMPT,
            format_evidence_block,
            format_support_block,
        )
        from app.knowledge.retrieve import retrieve_evidence
        from app.knowledge.taxonomy import (
            INSUFFICIENT_EVIDENCE_MESSAGE,
            OUT_OF_SCOPE_MESSAGE,
            build_retrieval_queries,
            classify_query,
            clip_chat_text,
            extract_pending_offer,
            is_short_affirmative,
            needs_deep_farm_context,
            needs_soil_lab_context,
        )
        from app.models.enums import DocumentStatus

        farm = self.farms.list_by_owner(owner_id)
        route = classify_query(text)
        answer_mode = route.answer_mode
        evidence = None
        sources: list[dict] = []
        answer_text = None
        agriser_ready = False
        if farm:
            agriser_ready = any(
                item.source_kind == "agriser_manual" and item.status == DocumentStatus.READY
                for item in self.knowledge.docs.list_for_farm(farm[0].id)
            )

        prior_all = [
            message
            for message in conversation.messages
            if message.id != user_message.id
            and message.role in {AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value}
        ]
        last_assistant = next(
            (item for item in reversed(prior_all) if item.role == AIMessageRole.ASSISTANT.value),
            None,
        )
        pending_offer = None
        if is_short_affirmative(text) and last_assistant is not None:
            pending_offer = extract_pending_offer(last_assistant.content or "")
        soil_lab_q = False
        field_observation = conversation.disease_case_id is not None
        has_chat_photo = bool(chat_photo_parts)
        # Photo-backed turns always go through advice+vision (not closed manual_fact).
        vision_turn = field_observation or has_chat_photo

        if (
            answer_mode == "manual_fact"
            and agriser_ready
            and not vision_turn
            and (route.out_of_scope or route.commercial or bool(route.document_keys) or bool(route.domains))
        ):
            evidence = retrieve_evidence(self.db, farm[0].id, text, agriser_only=True)
            sources = [
                {
                    "document_id": str(item.document_id),
                    "document_title": item.document_title,
                    "page_number": item.pages[0] if item.pages else None,
                    "section_title": item.section,
                    "excerpt": item.content[:200],
                }
                for item in evidence.sources[:4]
            ]
            if evidence.out_of_scope:
                answer_text = OUT_OF_SCOPE_MESSAGE
                knowledge_block = format_evidence_block(evidence, max_items=3, max_chars=450)
            elif not evidence.sufficient_evidence:
                answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
                knowledge_block = format_evidence_block(evidence, max_items=3, max_chars=450)
            else:
                knowledge_block = format_evidence_block(evidence, max_items=4, max_chars=500)
            system_prompt = AGRONOMY_SYSTEM_PROMPT
            chat_tools = None
            max_tool_rounds = 0
        else:
            # Advice mode (default): broader retrieval + softer prompt.
            # Light questions get a cheap FARM BRIEF; deep farm advice keeps tools.
            # Field observation / chat photo turns always stay in advice+vision path.
            system_prompt = ADVICE_SYSTEM_PROMPT if agriser_ready else SYSTEM_PROMPT
            soil_lab_q = needs_soil_lab_context(text) or bool(pending_offer)
            deep_farm = (
                needs_deep_farm_context(text)
                or soil_lab_q
                or bool(pending_offer)
                or field_observation
            )
            chat_tools = TOOL_SPECS if deep_farm else None
            max_tool_rounds = 2 if deep_farm else 0
            seen: set[tuple[str, int | None]] = set()
            merged: list[dict] = []
            queries = build_retrieval_queries(text, route) if agriser_ready else [text]
            if field_observation:
                queries = _field_observation_queries(text, conversation.title) + queries
            if has_chat_photo:
                queries = [text, "štetočine bolesti simptomi leska"] + queries
            for query in queries:
                hits = self.knowledge.search(owner_id, query, limit=4)
                for item in hits:
                    key = (str(item.document_id), item.page_number)
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(
                        {
                            "document_id": str(item.document_id),
                            "document_title": item.document_title,
                            "page_number": item.page_number,
                            "section_title": item.section_title,
                            "excerpt": item.content[:280],
                        }
                    )
                    if len(merged) >= 8:
                        break
                if len(merged) >= 8:
                    break
            sources = merged
            knowledge_block = format_support_block(sources, max_items=8, max_chars=450)
            farm_brief = self.context.format_parcel_brief(
                owner_id,
                parcel_id=conversation.parcel_id or parcel_id,
                include_soil_lab_text=soil_lab_q,
            )
            if farm_brief:
                knowledge_block = f"{farm_brief}\n\n{knowledge_block}"

        history = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="system", content=knowledge_block),
        ]
        case_block, case_photo_parts = self._problem_context(
            conversation,
            owner_id,
            # Always attach case photos in field threads so follow-ups can still "see" them.
            include_photos=field_observation,
        )
        photo_parts = [*chat_photo_parts, *case_photo_parts]
        if case_block:
            history.append(ChatMessage(role="system", content=case_block))
        if photo_parts:
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Priložene su fotografije U OVOJ korisničkoj poruci (image delovi). "
                        "Vi ih VIDITE — ne tvrđite da nemate pristup slici. "
                        "Obavezno ih vizuelno analizirajte: opišite što vidite, uporedite sa odlomcima "
                        "priručnika ako pomažu, dajte moguću identifikaciju kao sumnju (ne potvrdu) "
                        "i predložite sledeći korak."
                    ),
                )
            )
        if soil_lab_q and not pending_offer and answer_mode != "manual_fact":
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Korisnik traži mišljenje o laboratorijskoj analizi zemljišta. "
                        "Ako je pregled dug, pošaljite SAMO prvi deo (npr. pH / osnovni zaključak), "
                        "pa na kraju pitajte isključivo da li želi nastavak iste analize. "
                        "Izračun đubriva ili druge teme ostavite za kraj celog pregleda."
                    ),
                )
            )
        if pending_offer:
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "KORISNIK JE POTVRDIO VAŠU PRETHODNU PONUDU kratkim odgovorom.\n"
                        f"PONUDA KOJU TREBA ODMAH IZVRŠITI: {pending_offer}\n"
                        "Uradite tačno to što ste ponudili.\n"
                        "- Ako je ponuda bila nastavak ISTOG pregleda analize: nastavite sledeći deo analize "
                        "(npr. naredni parametri). Na kraju ovog dela opet pitajte samo za nastavak, "
                        "osim ako je ovo već poslednji deo.\n"
                        "- Ako je ponuda bila izračun/drugi korak na kraju: uradite taj korak sada.\n"
                        "Ne skrećite na novu temu i ne preskačite na izračun đubriva dok pregled analize nije završen."
                    ),
                )
            )
        # Keep only the latest few turns to reduce Gemini request size.
        for message in prior_all[-6:]:
            clipped = clip_chat_text(message.content or "", limit=1600)
            history.append(ChatMessage(role=message.role, content=clipped))
        user_content: str | list = text
        if photo_parts:
            user_content = [{"type": "text", "text": text}, *photo_parts]
        history.append(ChatMessage(role="user", content=user_content))

        structured_refs: list[dict] = []
        if answer_text:
            result_content = answer_text
            result_model = self.provider.chat_model
        else:
            result = self.provider.chat(history, tools=chat_tools)
            rounds = 0
            while result.tool_calls and rounds < max_tool_rounds:
                rounds += 1
                history.append(
                    ChatMessage(role="assistant", content=result.content or None, tool_calls=result.tool_calls)
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
                    tool_json = json.dumps(payload, default=str)
                    if len(tool_json) > 2500:
                        tool_json = tool_json[:2500] + "…"
                    history.append(
                        ChatMessage(
                            role="tool",
                            content=tool_json,
                            tool_call_id=call.id,
                        )
                    )
                # Last round: force a final answer without more tools.
                next_tools = None if rounds >= max_tool_rounds or not chat_tools else TOOL_SPECS
                result = self.provider.chat(history, tools=next_tools)
            result_content = (result.content or "").strip()
            result_model = result.model
            # Gemini sometimes ends a tool round with empty text — nudge one final answer.
            if not result_content:
                history.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "Sada OBAVEZNO napišite konačan odgovor korisniku na srpskom, latinicom. "
                            "Koristite FARM BRIEF i rezultate alata koje već imate. "
                            "Ne zovite nove alate i ne ostavljajte prazan odgovor."
                        ),
                    )
                )
                retry = self.provider.chat(history, tools=None)
                result_content = (retry.content or "").strip()
                result_model = retry.model or result_model
        answer = result_content or (
            "Trenutno nisam uspeo da sastavim odgovor iz dostupnih zapisa i priručnika. "
            "Probajte ponovo za trenutak, ili precizirajte pitanje (npr. parcela i šta tačno želite da ocenim)."
        )
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

    def _store_chat_photo(
        self,
        conversation: AIConversation,
        *,
        image: bytes,
        filename: str,
        content_type: str | None,
    ) -> tuple[dict, list[dict]]:
        mime = (content_type or "").split(";")[0].strip().lower()
        if mime == "image/jpg":
            mime = "image/jpeg"
        if mime and mime not in ALLOWED_CHAT_PHOTO_TYPES and mime != "application/octet-stream":
            raise AppError("Prihvataju se samo JPEG, PNG, WebP i GIF slike", status_code=422, code="invalid_photo")
        if len(image) > MAX_CHAT_PHOTO_BYTES:
            raise AppError("Fotografija je veća od 25 MB", status_code=422, code="photo_too_large")
        compressed = compress_photo(image, filename)
        key = f"chat/{conversation.id}/{uuid4().hex}{compressed.extension}"
        self.storage.put(key, compressed.content, compressed.content_type)
        ref = {
            "kind": "chat_image",
            "id": None,
            "label": compressed.filename,
            "extra": {
                "storage_key": key,
                "content_type": compressed.content_type,
                "size_bytes": len(compressed.content),
            },
        }
        encoded = base64.b64encode(compressed.content).decode("ascii")
        parts = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{compressed.content_type};base64,{encoded}"},
            }
        ]
        return ref, parts

    def get_message_image(self, conversation_id: UUID, message_id: UUID, owner_id: UUID) -> tuple[bytes, str, str]:
        conversation = self.get_conversation(conversation_id, owner_id)
        message = next((item for item in conversation.messages if item.id == message_id), None)
        if message is None:
            raise NotFoundError("Poruka nije pronađena")
        refs = message.structured_refs or []
        image_ref = next((item for item in refs if item.get("kind") == "chat_image"), None)
        if image_ref is None:
            raise NotFoundError("Fotografija nije pronađena")
        extra = image_ref.get("extra") or {}
        key = extra.get("storage_key")
        if not key:
            raise NotFoundError("Fotografija nije pronađena")
        content = self.storage.get(key)
        content_type = extra.get("content_type") or "image/jpeg"
        filename = image_ref.get("label") or "photo.jpg"
        return content, content_type, filename

    def _problem_context(
        self,
        conversation: AIConversation,
        owner_id: UUID,
        *,
        include_photos: bool,
    ) -> tuple[str | None, list[dict]]:
        if conversation.disease_case_id is None:
            return None, []

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
            "Ako su fotografije priložene u poruci, prvo ih komentarišite vizuelno.",
        ]
        photo_parts: list[dict] = []
        if include_photos:
            for photo in detail.photos[:3]:
                stored = diseases.get_photo(photo.id, owner_id)
                image, mime = diseases.photo_bytes(stored)
                # Shrink for chat vision payloads so Gemini reliably receives the image.
                compressed = compress_photo(image, stored.original_filename or "photo.jpg")
                image = compressed.content
                mime = compressed.content_type
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


def _field_observation_queries(content: str, title: str | None) -> list[str]:
    """Companion retrieval queries for pest/disease photo reviews."""
    from app.knowledge.taxonomy import fold

    folded = fold(f"{title or ''} {content}")
    queries = [
        (title or "").strip(),
        "štetočine i insekti na leski",
        "zaštita leske stenice i insekti",
    ]
    if "buba" in folded or "stenic" in folded:
        queries.extend(
            [
                "marmorirana stenica leska",
                "stenice štete na lešniku",
            ]
        )
    return [item for item in queries if item]
