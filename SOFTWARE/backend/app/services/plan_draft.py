"""Shared helpers for protection / nutrition / irrigation plan engines."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.context.engine import ContextEngine
from app.context.request import ContextRequest
from app.context.types import ContextRequestType
from app.knowledge.retrieve import retrieve_evidence
from app.models.enums import (
    PlanningExpertReviewStatus,
    PlanningItemKind,
    PlanningItemSource,
    PlanningItemStatus,
    PlanningPlanStatus,
    PlanningPlanType,
    PlanningPriorityLevel,
    PlanningScopeType,
    PlanningStream,
)
from app.models.planning import PlanningPlan, PlanningPlanItem, PlanningSeason
from app.repositories.planning import PlanningPlanItemRepository, PlanningPlanRepository

logger = logging.getLogger(__name__)

PRIORITY_SCORE = {
    PlanningPriorityLevel.HIGH: 90,
    PlanningPriorityLevel.MEDIUM: 50,
    PlanningPriorityLevel.LOW: 25,
    PlanningPriorityLevel.INFO: 10,
}

AGRISER_FALLBACK = (
    "Na osnovu dostupnih Agriser priručnika ne mogu pouzdano da utvrdim odgovor. "
    "Preporučujem proveru sa stručnim agronomom."
)

INSUFFICIENT = "Nedovoljno podataka za pouzdanu procenu."


@dataclass
class DraftPlanItem:
    title: str
    description: str
    reason: str
    item_kind: PlanningItemKind
    stream: PlanningStream
    source: PlanningItemSource
    status: PlanningItemStatus
    priority_level: PlanningPriorityLevel
    priority_reason: str
    scope_type: PlanningScopeType
    scope_id: UUID
    planned_date_from: date | None = None
    planned_date_to: date | None = None
    expert_review_status: PlanningExpertReviewStatus = PlanningExpertReviewStatus.NOT_REQUIRED
    evidence: list[dict] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    related_activity_id: UUID | None = None
    source_season_id: UUID | None = None
    source_plan_id: UUID | None = None
    source_plan_item_id: UUID | None = None


def ensure_plan(
    *,
    season: PlanningSeason,
    plan_type: PlanningPlanType,
    plans: PlanningPlanRepository,
    db: Session,
) -> PlanningPlan:
    for plan in season.plans:
        if plan.type == plan_type:
            return plan
    plan = PlanningPlan(
        planning_season_id=season.id,
        type=plan_type,
        status=PlanningPlanStatus.DRAFT,
        version=1,
    )
    plans.add(plan)
    db.flush()
    return plan


def clear_generated_items(plan: PlanningPlan, db: Session) -> None:
    removable = {
        PlanningItemSource.SYSTEM,
        PlanningItemSource.AGRONOMIC_RULE,
        PlanningItemSource.HISTORY,
    }
    for item in list(plan.items):
        if item.source in removable and item.status in {
            PlanningItemStatus.PLANNED,
            PlanningItemStatus.MONITOR,
            PlanningItemStatus.NEEDS_REVIEW,
        }:
            db.delete(item)
    db.flush()


def persist_drafts(
    *,
    plan: PlanningPlan,
    drafts: list[DraftPlanItem],
    items: PlanningPlanItemRepository,
    db: Session,
) -> None:
    for draft in drafts:
        items.add(
            PlanningPlanItem(
                plan_id=plan.id,
                scope_type=draft.scope_type,
                scope_id=draft.scope_id,
                title=draft.title[:255],
                description=draft.description,
                planned_date_from=draft.planned_date_from,
                planned_date_to=draft.planned_date_to,
                priority=PRIORITY_SCORE[draft.priority_level],
                priority_level=draft.priority_level,
                priority_reason=draft.priority_reason,
                item_kind=draft.item_kind,
                stream=draft.stream,
                reason=draft.reason,
                evidence=draft.evidence,
                missing_data=draft.missing_data,
                related_activity_id=draft.related_activity_id,
                status=draft.status,
                source=draft.source,
                expert_review_status=draft.expert_review_status,
                source_season_id=draft.source_season_id,
                source_plan_id=draft.source_plan_id,
                source_plan_item_id=draft.source_plan_item_id,
            )
        )
    if plan.status == PlanningPlanStatus.DRAFT and drafts:
        plan.status = PlanningPlanStatus.READY_FOR_REVIEW


def knowledge_citations(db: Session, *, farm_id: UUID, question: str) -> tuple[list[dict], str | None]:
    try:
        package = retrieve_evidence(db, farm_id, question, agriser_only=True)
    except Exception:
        logger.exception("Knowledge retrieval failed")
        return [], AGRISER_FALLBACK
    if not package.sources or not package.sufficient_evidence:
        return [], AGRISER_FALLBACK
    citations: list[dict] = []
    for source in package.sources[:5]:
        citations.append(
            {
                "document_id": str(source.document_id) if source.document_id else None,
                "document_title": source.document_title,
                "pages": list(source.pages or []),
                "section": source.section,
                "chunk_id": str(source.chunk_id) if source.chunk_id else None,
                "score": source.score,
            }
        )
    return citations, None


def season_context(db: Session, owner_id: UUID, parcel_id: UUID):
    request = ContextRequest(
        request_type=ContextRequestType.SEASON_ANALYSIS,
        parcel_id=parcel_id,
        include_debug=False,
    )
    return ContextEngine(db).build_context(owner_id, request)
