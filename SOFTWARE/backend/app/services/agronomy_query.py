from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.base import ChatMessage
from app.ai.prompts import AGRONOMY_SYSTEM_PROMPT, format_evidence_block
from app.core.exceptions import NotFoundError
from app.knowledge.retrieve import retrieve_evidence
from app.knowledge.taxonomy import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    PRODUCT_GUESS_MESSAGE,
)
from app.repositories.farm import FarmRepository
from app.schemas.knowledge import AgronomyQueryResponse, EvidencePackage


class AgronomyQueryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.farms = FarmRepository(db)
        self.provider = get_ai_provider()

    def query(
        self,
        owner_id: UUID,
        question: str,
        *,
        mode: str = "retrieve",
        include_images: bool = False,
        debug: bool = False,
    ) -> AgronomyQueryResponse:
        farm = self.farms.list_by_owner(owner_id)
        if not farm:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        evidence = retrieve_evidence(
            self.db,
            farm[0].id,
            question,
            agriser_only=True,
            include_images=include_images,
        )
        answer = self._answer_from_evidence(question, evidence, mode=mode)
        citations = _citations(evidence)
        return AgronomyQueryResponse(
            question=question,
            mode=mode,
            sufficient_evidence=evidence.sufficient_evidence,
            out_of_scope=evidence.out_of_scope,
            answer=answer,
            citations=citations,
            evidence=evidence if debug or mode == "retrieve" else evidence.model_copy(update={"debug": None}),
            debug=evidence.debug if debug else None,
        )

    def _answer_from_evidence(self, question: str, evidence: EvidencePackage, *, mode: str) -> str:
        if evidence.out_of_scope:
            return OUT_OF_SCOPE_MESSAGE
        if evidence.commercial:
            return PRODUCT_GUESS_MESSAGE
        if not evidence.sufficient_evidence:
            return INSUFFICIENT_EVIDENCE_MESSAGE
        if mode == "retrieve":
            return _retrieve_summary(evidence)
        block = format_evidence_block(evidence)
        result = self.provider.chat(
            [
                ChatMessage(role="system", content=AGRONOMY_SYSTEM_PROMPT),
                ChatMessage(role="system", content=block),
                ChatMessage(role="user", content=question),
            ]
        )
        text = (result.content or "").strip()
        return text or _retrieve_summary(evidence)


def _citations(evidence: EvidencePackage) -> list[str]:
    rows = []
    for item in evidence.sources + evidence.tables + evidence.formulas:
        pages = ", ".join(str(page) for page in item.pages) if item.pages else "?"
        section = f", poglavlje '{item.section}'" if item.section else ""
        rows.append(f"{item.document_title}, str. {pages}{section}")
    return list(dict.fromkeys(rows))


def _retrieve_summary(evidence: EvidencePackage) -> str:
    if not evidence.sources and not evidence.tables:
        return INSUFFICIENT_EVIDENCE_MESSAGE
    lines = ["Pronađeni odlomci iz Agriser priručnika:", ""]
    for item in (evidence.sources + evidence.tables)[:6]:
        pages = "-".join(str(page) for page in item.pages) if item.pages else "?"
        lines.append(f"- {item.document_title}, str. {pages}, {item.section or 'n/a'}")
        lines.append(item.content[:500])
        lines.append("")
    lines.append("Izvor: " + "; ".join(_citations(evidence)[:4]))
    return "\n".join(lines).strip()
