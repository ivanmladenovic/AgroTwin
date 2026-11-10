from __future__ import annotations

import base64
import json
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.base import ChatMessage
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
ALLOWED_CHAT_PDF_TYPES = {"application/pdf", "application/x-pdf"}
# Client converts HEIC→PNG and downscales first; keep headroom for large phone photos / PDFs.
MAX_CHAT_PHOTO_BYTES = 25 * 1024 * 1024
MAX_CHAT_PDF_BYTES = 25 * 1024 * 1024
CHAT_PHOTO_PLACEHOLDER = "Pogledajte priloženu fotografiju."
CHAT_PDF_PLACEHOLDER = "Pogledajte priloženi PDF dokument."
MAX_CHAT_PDF_TEXT_CHARS = 12_000
MAX_CHAT_PDF_VISION_PAGES = 2


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
                if ref.get("kind") not in {"chat_image", "chat_document"}:
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
        locale: str = "sr",
    ) -> AIConversation:
        conversation = self.get_conversation(conversation_id, owner_id)
        if parcel_id:
            conversation.parcel_id = parcel_id

        text = (content or "").strip()
        attachment_refs: list[dict] = []
        chat_photo_parts: list[dict] = []
        document_text: str | None = None
        if image is not None:
            attachment_refs, chat_photo_parts, document_text, placeholder = self._store_chat_attachment(
                conversation,
                payload=image,
                filename=image_filename or "attachment",
                content_type=image_content_type,
            )
            if not text:
                text = placeholder
            self._remember_lab_reading(
                conversation,
                owner_id,
                attachment_refs,
                filename=image_filename,
                content_type=image_content_type,
            )
            # The report was already sent to the model above. Do not attach the
            # same page images again on the reply turn — that second vision call
            # is what leaves "Agronom piše" hanging.
            if any(ref.get("kind") == "chat_document" for ref in attachment_refs):
                chat_photo_parts = []

        if not text:
            raise AppError("Poruka ne sme biti prazna", status_code=422, code="empty_message")

        if conversation.title in {"Orchard question", "Pitanje o voćnjaku"}:
            conversation.title = text[:80]
        user_message = AIMessage(
            conversation_id=conversation.id,
            role=AIMessageRole.USER.value,
            content=text,
            structured_refs=attachment_refs or None,
        )
        self.conversations.add_message(user_message)
        self.db.flush()

        from app.ai.prompts import (
            format_evidence_block,
            format_support_block,
            get_advice_system_prompt,
            get_agronomy_system_prompt,
            get_system_prompt,
        )
        from app.core.locale import effective_reply_locale, REPLY_LANGUAGE_INSTRUCTION_EN
        from app.knowledge.retrieve import retrieve_evidence
        from app.knowledge.taxonomy import (
            build_retrieval_queries,
            insufficient_evidence_message,
            out_of_scope_message,
            classify_query,
            clip_chat_text,
            extract_pending_offer,
            is_short_affirmative,
            needs_deep_farm_context,
            needs_soil_lab_context,
        )
        from app.soil.lab_vision import format_lab_reading, remembered_lab_block

        current_reading_raw = _lab_reading_from_refs(attachment_refs)
        current_reading = format_lab_reading(current_reading_raw)
        from app.models.enums import DocumentStatus

        reply_locale = effective_reply_locale(locale, text)

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
        remembered_lab = remembered_lab_block(prior_all)
        field_observation = conversation.disease_case_id is not None
        has_chat_photo = bool(chat_photo_parts)
        has_chat_document = bool(document_text) or any(
            ref.get("kind") == "chat_document" for ref in attachment_refs
        )
        # Photo/PDF-backed turns always go through advice+vision (not closed manual_fact).
        vision_turn = field_observation or has_chat_photo or has_chat_document

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
                answer_text = out_of_scope_message(reply_locale)
                knowledge_block = format_evidence_block(
                    evidence, max_items=3, max_chars=450, locale=reply_locale
                )
            elif not evidence.sufficient_evidence:
                answer_text = insufficient_evidence_message(reply_locale)
                knowledge_block = format_evidence_block(
                    evidence, max_items=3, max_chars=450, locale=reply_locale
                )
            else:
                knowledge_block = format_evidence_block(
                    evidence, max_items=4, max_chars=500, locale=reply_locale
                )
            system_prompt = get_agronomy_system_prompt(reply_locale)
            chat_tools = None
            max_tool_rounds = 0
        else:
            # Advice mode (default): broader retrieval + softer prompt.
            # Light questions get a cheap FARM BRIEF; deep farm advice keeps tools.
            # Field observation / chat photo turns always stay in advice+vision path.
            system_prompt = (
                get_advice_system_prompt(reply_locale) if agriser_ready else get_system_prompt(reply_locale)
            )
            soil_lab_q = needs_soil_lab_context(text) or bool(pending_offer) or bool(remembered_lab) or has_chat_document
            deep_farm = (
                needs_deep_farm_context(text)
                or soil_lab_q
                or bool(pending_offer)
                or field_observation
            )
            chat_tools = TOOL_SPECS if deep_farm else None
            max_tool_rounds = 2 if deep_farm else 0
            if current_reading:
                # Parameters are already read. One text reply, no extra tool rounds.
                chat_tools = None
                max_tool_rounds = 0
            seen: set[tuple[str, int | None]] = set()
            merged: list[dict] = []
            queries = build_retrieval_queries(text, route) if agriser_ready else [text]
            if field_observation:
                queries = _field_observation_queries(text, conversation.title) + queries
            if has_chat_photo:
                queries = [text, "štetočine bolesti simptomi leska"] + queries
            if has_chat_document:
                queries = [text, "analiza zemljišta leska", "đubrenje leske"] + queries
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
            knowledge_block = format_support_block(
                sources, max_items=8, max_chars=450, locale=reply_locale
            )
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
        if reply_locale == "en":
            history.append(ChatMessage(role="system", content=REPLY_LANGUAGE_INSTRUCTION_EN))
        case_block, case_photo_parts = self._problem_context(
            conversation,
            owner_id,
            # Always attach case photos in field threads so follow-ups can still "see" them.
            include_photos=field_observation,
        )
        photo_parts = [*chat_photo_parts, *case_photo_parts]
        if case_block:
            history.append(ChatMessage(role="system", content=case_block))
        if current_reading:
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "MODEL JE U OVOJ PORUCI PROČITAO LABORATORIJSKU ANALIZU. "
                        "Odmah protumači najbitnije parametre iz ovog izvoda. "
                        "Ne traži ponovo dokument i ne reci da analiza nije priložena. "
                        "Ako nekog parametra nema u izvodu, reci da nije naveden. "
                        "Ne pretvaraj nedostajuće u nulu.\n\n"
                        f"{current_reading}"
                    ),
                )
            )
        elif remembered_lab:
            history.append(ChatMessage(role="system", content=remembered_lab))
        elif current_reading_raw and current_reading_raw.get("error"):
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Laboratorijski PDF je upravo priložen, ali čitanje parametara nije uspelo: "
                        f"{current_reading_raw.get('error')} "
                        "Reci to korisniku i ne traži isti dokument ponovo u istoj poruci. "
                        "Ne izmišljaj brojeve."
                    ),
                )
            )
        if document_text:
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Korisnik je priložio PDF dokument u ovoj poruci. "
                        "Ispod je izvučeni tekst (može biti nepotpun ako je PDF skeniran). "
                        "Koristite ga kao izvor činjenica iz dokumenta; ne izmišljajte vrednosti koje nisu navedene.\n\n"
                        f"{document_text}"
                    ),
                )
            )
        if photo_parts:
            history.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Priložene su fotografije / stranice dokumenta U OVOJ korisničkoj poruci (image delovi). "
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
                        "Ako je izvod analize već u ovom razgovoru, odmah protumači najbitnije parametre "
                        "(pH, humus, azot, fosfor, kalijum i ono što je navedeno). "
                        "Ne traži ponovo upload. Izračun đubriva ostavi za sledeći korak, "
                        "tek ako korisnik to zatraži."
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

    def _remember_lab_reading(
        self,
        conversation: AIConversation,
        owner_id: UUID,
        refs: list[dict],
        *,
        filename: str | None,
        content_type: str | None,
    ) -> None:
        document = next((ref for ref in refs if ref.get("kind") == "chat_document"), None)
        if document is None:
            return
        extra = dict(document.get("extra") or {})
        key = extra.get("storage_key")
        if not isinstance(key, str) or not key:
            return
        try:
            payload = self.storage.get(key)
        except Exception:
            return
        from app.soil.lab_vision import read_lab_document

        reading = read_lab_document(self.provider, payload, content_type or extra.get("content_type"))
        extra["lab_reading"] = {
            "laboratory_name": reading.get("laboratory_name"),
            "sampled_on": reading.get("sampled_on"),
            "summary": reading.get("summary"),
            "parameters": reading.get("parameters") or [],
            "error": reading.get("error"),
        }
        parcel_id = conversation.parcel_id or self._sole_parcel_id(owner_id)
        if parcel_id is not None:
            analysis_id = self._file_lab_on_parcel(
                owner_id,
                parcel_id,
                filename=filename or document.get("label") or "analiza.pdf",
                content_type=content_type or extra.get("content_type") or "application/pdf",
                payload=payload,
                reading=reading,
            )
            if analysis_id is not None:
                extra["soil_analysis_id"] = str(analysis_id)
                extra["parcel_id"] = str(parcel_id)
                conversation.parcel_id = parcel_id
        document["extra"] = extra

    def _sole_parcel_id(self, owner_id: UUID) -> UUID | None:
        from app.repositories.parcel import ParcelRepository

        parcels = ParcelRepository(self.db).list_for_owner(owner_id)
        if len(parcels) == 1:
            return parcels[0].id
        return None

    def _file_lab_on_parcel(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        *,
        filename: str,
        content_type: str,
        payload: bytes,
        reading: dict,
    ) -> UUID | None:
        from datetime import date

        from app.services.soil_lab import SoilLabAnalysisService

        labs = SoilLabAnalysisService(self.db)
        trees = labs.trees.list_options(parcel_id)
        if not trees:
            return None
        sampled = date.today()
        raw_date = reading.get("sampled_on")
        if isinstance(raw_date, str) and raw_date:
            try:
                sampled = date.fromisoformat(raw_date[:10])
            except ValueError:
                sampled = date.today()
        try:
            analysis = labs.create(
                labs._ensure_soil_activity(
                    labs._parcel(parcel_id, owner_id),
                    sampled,
                    owner_id,
                    owner_id,
                ).id,
                owner_id,
                tree_id=trees[0][0].id,
                sampled_on=sampled,
                filename=filename,
                content_type=content_type,
                content=payload,
                created_by_id=owner_id,
                reading=reading,
            )
        except Exception:
            return None
        return analysis.id

    def _store_chat_attachment(
        self,
        conversation: AIConversation,
        *,
        payload: bytes,
        filename: str,
        content_type: str | None,
    ) -> tuple[list[dict], list[dict], str | None, str]:
        mime = (content_type or "").split(";")[0].strip().lower()
        if mime == "image/jpg":
            mime = "image/jpeg"
        name = (filename or "").lower()
        is_pdf = mime in ALLOWED_CHAT_PDF_TYPES or name.endswith(".pdf")
        if is_pdf:
            return self._store_chat_pdf(
                conversation,
                payload=payload,
                filename=filename or "dokument.pdf",
                content_type=mime or "application/pdf",
            )
        ref, parts = self._store_chat_photo(
            conversation,
            image=payload,
            filename=filename or "photo.jpg",
            content_type=mime or content_type,
        )
        return [ref], parts, None, CHAT_PHOTO_PLACEHOLDER

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
            raise AppError(
                "Prihvataju se JPEG, PNG, WebP, GIF ili PDF",
                status_code=422,
                code="invalid_attachment",
            )
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

    def _store_chat_pdf(
        self,
        conversation: AIConversation,
        *,
        payload: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[list[dict], list[dict], str | None, str]:
        if not payload.startswith(b"%PDF"):
            raise AppError("Fajl nije validan PDF", status_code=422, code="invalid_pdf")
        if len(payload) > MAX_CHAT_PDF_BYTES:
            raise AppError("PDF je veći od 25 MB", status_code=422, code="pdf_too_large")

        from app.knowledge.pdf import extract_pdf_pages

        safe_name = (filename or "dokument.pdf").strip() or "dokument.pdf"
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{safe_name}.pdf"
        key = f"chat/{conversation.id}/{uuid4().hex}.pdf"
        self.storage.put(key, payload, content_type or "application/pdf")

        pages = extract_pdf_pages(payload)
        joined = "\n\n".join(f"[Strana {number}]\n{text}" for number, text in pages).strip()
        document_text = joined[:MAX_CHAT_PDF_TEXT_CHARS] if joined else None
        if document_text and len(joined) > MAX_CHAT_PDF_TEXT_CHARS:
            document_text = f"{document_text}\n\n[…tekst skraćen…]"

        vision_parts: list[dict] = []
        # Scanned / low-text PDFs: render first pages for vision models.
        if len(joined) < 400:
            vision_parts = self._pdf_page_image_parts(payload)

        ref = {
            "kind": "chat_document",
            "id": None,
            "label": safe_name,
            "extra": {
                "storage_key": key,
                "content_type": content_type or "application/pdf",
                "size_bytes": len(payload),
                "page_count": len(pages) or None,
                "has_extracted_text": bool(joined),
                "vision_pages": len(vision_parts),
            },
        }
        return [ref], vision_parts, document_text, CHAT_PDF_PLACEHOLDER

    def _pdf_page_image_parts(self, payload: bytes) -> list[dict]:
        try:
            import fitz
        except ImportError:
            return []
        try:
            document = fitz.open(stream=payload, filetype="pdf")
        except Exception:
            return []
        parts: list[dict] = []
        try:
            matrix = fitz.Matrix(1.5, 1.5)
            for page in list(document)[:MAX_CHAT_PDF_VISION_PAGES]:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                jpeg = pixmap.tobytes("jpeg")
                if len(jpeg) > 4_000_000:
                    continue
                encoded = base64.b64encode(jpeg).decode("ascii")
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    }
                )
        finally:
            document.close()
        return parts

    def get_message_image(self, conversation_id: UUID, message_id: UUID, owner_id: UUID) -> tuple[bytes, str, str]:
        conversation = self.get_conversation(conversation_id, owner_id)
        message = next((item for item in conversation.messages if item.id == message_id), None)
        if message is None:
            raise NotFoundError("Poruka nije pronađena")
        refs = message.structured_refs or []
        attachment_ref = next(
            (item for item in refs if item.get("kind") in {"chat_image", "chat_document"}),
            None,
        )
        if attachment_ref is None:
            raise NotFoundError("Prilog nije pronađen")
        extra = attachment_ref.get("extra") or {}
        key = extra.get("storage_key")
        if not key:
            raise NotFoundError("Prilog nije pronađen")
        content = self.storage.get(key)
        content_type = extra.get("content_type") or (
            "application/pdf" if attachment_ref.get("kind") == "chat_document" else "image/jpeg"
        )
        filename = attachment_ref.get("label") or (
            "dokument.pdf" if attachment_ref.get("kind") == "chat_document" else "photo.jpg"
        )
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


def _lab_reading_from_refs(refs: list[dict]) -> dict | None:
    for ref in refs:
        reading = (ref.get("extra") or {}).get("lab_reading")
        if isinstance(reading, dict):
            return reading
    return None


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
