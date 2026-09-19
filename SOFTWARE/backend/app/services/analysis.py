from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.prompts import ANALYSIS_DISCLAIMER, ANALYSIS_PROMPT
from app.core.exceptions import AppError, NotFoundError
from app.models.analysis import DiseaseAnalysis
from app.models.enums import AttachmentEntityType
from app.repositories.ai import AnalysisRepository
from app.schemas.ai import DiseaseAnalysisRead
from app.services.disease import DiseaseService
from app.services.farm_context import FarmContextService
from app.services.knowledge import KnowledgeService


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.analyses = AnalysisRepository(db)
        self.diseases = DiseaseService(db)
        self.context = FarmContextService(db)
        self.knowledge = KnowledgeService(db)
        self.provider = get_ai_provider()

    def list_for_case(self, case_id: UUID, owner_id: UUID) -> list[DiseaseAnalysisRead]:
        self.diseases.get_case(case_id, owner_id)
        return [self.to_read(item) for item in self.analyses.list_for_case(case_id)]

    def analyze(
        self,
        case_id: UUID,
        owner_id: UUID,
        *,
        photo_id: UUID | None,
        notes: str | None,
    ) -> DiseaseAnalysis:
        case = self.diseases.get_case(case_id, owner_id)
        photo = None
        image = b""
        mime = "image/png"
        if photo_id is not None:
            photo = self.diseases.get_photo(photo_id, owner_id)
            if photo.entity_type not in {
                AttachmentEntityType.OBSERVATION,
                AttachmentEntityType.DISEASE_CASE,
                AttachmentEntityType.TREE,
            }:
                raise AppError("Ova fotografija se ne može koristiti za analizu", status_code=422)
            image, mime = self.diseases.photo_bytes(photo)
        elif case.tree_id is not None:
            photos = self.diseases.tree_photos(case.tree_id, [case])
            if photos:
                photo = self.diseases.get_photo(photos[0].id, owner_id)
                image, mime = self.diseases.photo_bytes(photo)

        query = " ".join(
            part
            for part in (case.title, case.description, case.notes, notes, case.category.value)
            if part
        )
        hits = self.knowledge.search(owner_id, query or "simptomi lesnika", limit=5)
        knowledge_text = "\n\n".join(
            f"{item.document_title} (strana {item.page_number or '-'}): {item.content[:400]}" for item in hits
        ) or "Nema odgovarajućeg odlomka iz priručnika."
        tree_context = self.context.tree_context_for_analysis(owner_id, case.tree_id, case.parcel_id)
        prompt = ANALYSIS_PROMPT.format(
            disclaimer=ANALYSIS_DISCLAIMER,
            context=(
                f"Slučaj: {case.title}\nKategorija: {case.category.value}\nOzbiljnost: {case.severity.value}\n"
                f"Beleške proizvođača: {case.description or case.notes or '-'}\nDodatne beleške: {notes or '-'}\n"
                f"Kontekst stabla: {tree_context}"
            ),
            knowledge=knowledge_text,
        )
        if not image:
            image = b"\x89PNG"
            mime = "image/png"
        result = self.provider.analyze_image(image, mime, prompt, json_mode=True)
        analysis = DiseaseAnalysis(
            farm_id=case.farm_id,
            disease_case_id=case.id,
            photo_id=photo.id if photo is not None else None,
            likely_issue=result.likely_issue,
            confidence=max(0.0, min(1.0, result.confidence)),
            observed_symptoms=result.observed_symptoms,
            possible_alternatives=result.possible_alternatives,
            recommended_inspection=result.recommended_inspection,
            recommended_next_step=result.recommended_next_step,
            supporting_sources=[
                {
                    "document_id": str(item.document_id),
                    "document_title": item.document_title,
                    "page_number": item.page_number,
                    "excerpt": item.content[:240],
                }
                for item in hits
            ],
            observed_facts=result.observed_facts,
            uncertainty_notes=result.uncertainty_notes,
            disclaimer=result.disclaimer or ANALYSIS_DISCLAIMER,
            provider=self.provider.name,
            model=result.model,
        )
        self.analyses.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def to_read(self, item: DiseaseAnalysis) -> DiseaseAnalysisRead:
        return DiseaseAnalysisRead(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            farm_id=item.farm_id,
            disease_case_id=item.disease_case_id,
            photo_id=item.photo_id,
            likely_issue=item.likely_issue,
            confidence=item.confidence,
            observed_symptoms=item.observed_symptoms or [],
            possible_alternatives=item.possible_alternatives or [],
            recommended_inspection=item.recommended_inspection,
            recommended_next_step=item.recommended_next_step,
            supporting_sources=item.supporting_sources or [],
            observed_facts=item.observed_facts,
            uncertainty_notes=item.uncertainty_notes,
            disclaimer=item.disclaimer,
            provider=item.provider,
            model=item.model,
        )
