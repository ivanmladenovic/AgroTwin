"""Expert review workflow for planning recommendations.

AgroTwin generates a proposal → expert APPROVE / MODIFY / REJECT → only then is it
approved for application. Original snapshots are never overwritten without history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.enums import (
    ExpertReviewStatus,
    PlanningExpertReviewStatus,
    PlanningItemStatus,
    PlanningPlanStatus,
)
from app.models.farm import Farm
from app.models.planning import ExpertReview, PlanningPlan, PlanningPlanItem, PlanningSeason
from app.models.user import User
from app.repositories.planning import PlanningPlanRepository
from app.schemas.planning import ExpertReviewDecisionRequest, ExpertReviewSubmitRequest


def _item_snapshot(item: PlanningPlanItem, *, season: PlanningSeason | None = None) -> dict:
    plan = item.plan
    season = season or (plan.season if plan is not None else None)
    return {
        "plan_item_id": str(item.id),
        "title": item.title,
        "description": item.description,
        "reason": item.reason,
        "priority_level": item.priority_level.value if item.priority_level else None,
        "priority_reason": item.priority_reason,
        "item_kind": item.item_kind.value if item.item_kind else None,
        "stream": item.stream.value if item.stream else None,
        "status": item.status.value if item.status else None,
        "source": item.source.value if item.source else None,
        "expert_review_status": item.expert_review_status.value if item.expert_review_status else None,
        "scope_type": item.scope_type.value if item.scope_type else None,
        "scope_id": str(item.scope_id),
        "planned_date_from": item.planned_date_from.isoformat() if item.planned_date_from else None,
        "planned_date_to": item.planned_date_to.isoformat() if item.planned_date_to else None,
        "evidence": list(item.evidence or []),
        "missing_data": list(item.missing_data or []),
        "related_activity_id": str(item.related_activity_id) if item.related_activity_id else None,
        "source_season_id": str(item.source_season_id) if item.source_season_id else None,
        "source_plan_id": str(item.source_plan_id) if item.source_plan_id else None,
        "source_plan_item_id": str(item.source_plan_item_id) if item.source_plan_item_id else None,
        "parcel_id": str(season.parcel_id) if season else None,
        "season_year": season.year if season else None,
        "plan_type": plan.type.value if plan and plan.type else None,
        "uncertainty": list(item.missing_data or []),
    }


class ExpertReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.plans = PlanningPlanRepository(db)

    def list_for_item(self, plan_id: UUID, item_id: UUID, owner_id: UUID) -> list[ExpertReview]:
        item = self._owned_item(plan_id, item_id, owner_id)
        return list(item.expert_reviews or [])

    def submit(
        self,
        plan_id: UUID,
        item_id: UUID,
        owner_id: UUID,
        requester: User,
        payload: ExpertReviewSubmitRequest | None = None,
    ) -> ExpertReview:
        item = self._owned_item(plan_id, item_id, owner_id)
        season = item.plan.season
        # Close any open pending review as superseded by creating a new pending trail entry
        # without deleting history.
        open_pending = [
            row
            for row in (item.expert_reviews or [])
            if row.status == ExpertReviewStatus.PENDING
        ]
        for row in open_pending:
            row.comment = (row.comment or "") + "\n[superseded by new submit]"
            row.status = ExpertReviewStatus.REJECTED
            row.reviewed_at = datetime.now(timezone.utc)
            row.reviewer_name = row.reviewer_name or "system"
            row.reviewed_recommendation_snapshot = {
                "note": "Superseded — new expert review request was submitted.",
            }

        snapshot = _item_snapshot(item, season=season)
        if payload and payload.note:
            snapshot["submit_note"] = payload.note.strip()

        review = ExpertReview(
            plan_item_id=item.id,
            farm_id=season.farm_id,
            requested_by_id=requester.id,
            status=ExpertReviewStatus.PENDING,
            original_recommendation_snapshot=snapshot,
            comment=payload.note.strip() if payload and payload.note else None,
        )
        self.db.add(review)
        item.expert_review_status = PlanningExpertReviewStatus.PENDING
        item.status = PlanningItemStatus.NEEDS_REVIEW
        if item.plan.status in {PlanningPlanStatus.DRAFT, PlanningPlanStatus.READY_FOR_REVIEW}:
            item.plan.status = PlanningPlanStatus.EXPERT_REVIEW
        self.db.commit()
        self.db.expire_all()
        loaded = self.db.get(ExpertReview, review.id)
        assert loaded is not None
        return loaded

    def decide(
        self,
        plan_id: UUID,
        item_id: UUID,
        review_id: UUID,
        owner_id: UUID,
        reviewer: User,
        payload: ExpertReviewDecisionRequest,
    ) -> ExpertReview:
        item = self._owned_item(plan_id, item_id, owner_id)
        self._assert_can_review(reviewer, item.plan.season.farm_id)
        review = next((row for row in (item.expert_reviews or []) if row.id == review_id), None)
        if review is None:
            raise NotFoundError("Stručna provera nije pronađena")
        if review.farm_id != item.plan.season.farm_id:
            raise ForbiddenError("Nije dozvoljen pristup tuđoj stručnoj proveri")
        if review.status != ExpertReviewStatus.PENDING:
            raise AppError("Ova provera je već zatvorena.", status_code=409, code="review_closed")

        decision = payload.status
        if decision not in {
            ExpertReviewStatus.APPROVED,
            ExpertReviewStatus.MODIFIED,
            ExpertReviewStatus.REJECTED,
        }:
            raise AppError("Nedozvoljen status odluke.", status_code=422, code="invalid_decision")

        original = dict(review.original_recommendation_snapshot or _item_snapshot(item, season=item.plan.season))
        reviewed_snap = dict(original)

        if decision == ExpertReviewStatus.MODIFIED:
            if payload.title:
                item.title = payload.title.strip()[:255]
            if payload.description is not None:
                item.description = (payload.description or "").strip() or None
            if payload.reason is not None:
                item.reason = (payload.reason or "").strip() or None
            if payload.priority_level is not None:
                item.priority_level = payload.priority_level
            reviewed_snap = _item_snapshot(item, season=item.plan.season)
            reviewed_snap["modification_comment"] = (payload.comment or "").strip() or None
            item.expert_review_status = PlanningExpertReviewStatus.MODIFIED
            item.status = PlanningItemStatus.APPROVED
        elif decision == ExpertReviewStatus.APPROVED:
            reviewed_snap["decision"] = "approved"
            item.expert_review_status = PlanningExpertReviewStatus.APPROVED
            item.status = PlanningItemStatus.APPROVED
        else:
            reviewed_snap["decision"] = "rejected"
            item.expert_review_status = PlanningExpertReviewStatus.REJECTED
            item.status = PlanningItemStatus.CANCELLED

        review.status = decision
        review.reviewer_id = reviewer.id
        review.reviewer_name = reviewer.full_name
        review.reviewed_at = datetime.now(timezone.utc)
        review.comment = (payload.comment or "").strip() or review.comment
        review.original_recommendation_snapshot = original
        review.reviewed_recommendation_snapshot = reviewed_snap

        self.db.commit()
        self.db.expire_all()
        loaded = self.db.get(ExpertReview, review.id)
        assert loaded is not None
        return loaded

    def _owned_item(self, plan_id: UUID, item_id: UUID, owner_id: UUID) -> PlanningPlanItem:
        stmt = (
            select(PlanningPlanItem)
            .options(
                selectinload(PlanningPlanItem.expert_reviews),
                selectinload(PlanningPlanItem.plan).selectinload(PlanningPlan.season),
            )
            .join(PlanningPlan, PlanningPlanItem.plan_id == PlanningPlan.id)
            .join(PlanningSeason, PlanningPlan.planning_season_id == PlanningSeason.id)
            .join(Farm, PlanningSeason.farm_id == Farm.id)
            .where(
                PlanningPlanItem.id == item_id,
                PlanningPlanItem.plan_id == plan_id,
                Farm.owner_id == owner_id,
            )
        )
        item = self.db.scalars(stmt).unique().first()
        if item is None:
            raise NotFoundError("Stavka plana nije pronađena")
        return item

    def _assert_can_review(self, reviewer: User, farm_id: UUID) -> None:
        """Farm owner or superuser may act as expert reviewer (no separate role table yet)."""
        if reviewer.is_superuser:
            return
        farm = self.db.get(Farm, farm_id)
        if farm is None or farm.owner_id != reviewer.id:
            raise ForbiddenError("Nemate ovlašćenje za stručnu proveru na ovom gazdinstvu")
