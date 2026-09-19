from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import DiseaseCaseStatus, ScopeType
from app.repositories.activity import ActivityRepository
from app.repositories.cost import CostRepository
from app.repositories.disease import DiseaseRepository
from app.schemas.journal import TimelineEvent, TreeJournalRead
from app.services.activity import ActivityService
from app.services.disease import DiseaseService
from app.services.orchard import OrchardService


class JournalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orchard = OrchardService(db)
        self.activities = ActivityService(db)
        self.activity_repo = ActivityRepository(db)
        self.costs = CostRepository(db)
        self.disease_repo = DiseaseRepository(db)
        self.diseases = DiseaseService(db)

    def get_tree_journal(self, parcel_id: UUID, tree_id: UUID, owner_id: UUID) -> TreeJournalRead:
        tree = self.orchard.get_tree_detail(parcel_id, tree_id, owner_id)
        direct = [
            self.activities.to_activity_read(item)
            for item in self.activity_repo.list_for_owner(owner_id, tree_id=tree.id)
        ]
        row_activities = [
            self.activities.to_activity_read(item)
            for item in self.activity_repo.list_for_owner(
                owner_id, row_id=tree.row_id, scope_type=ScopeType.ROW
            )
        ]
        parcel_activities = [
            self.activities.to_activity_read(item)
            for item in self.activity_repo.list_for_owner(
                owner_id, parcel_id=tree.parcel_id, scope_type=ScopeType.PARCEL
            )
        ]
        related = row_activities + parcel_activities
        case_models = self.disease_repo.list_for_tree(tree.id)
        diseases = [self.diseases.to_case_read(item) for item in case_models]
        open_cases = [item for item in diseases if item.status != DiseaseCaseStatus.RESOLVED]
        observations = [
            self.diseases.to_observation_read(observation)
            for case in case_models
            for observation in self.diseases.observations.list_for_case(case.id)
        ]
        observations.sort(key=lambda item: (item.observed_on, item.created_at), reverse=True)
        photos = self.diseases.tree_photos(tree.id, case_models)
        direct_costs = [cost for activity in direct for cost in activity.costs]
        related_costs = [cost for activity in related for cost in activity.costs]
        direct_total = sum((item.amount for item in direct_costs), Decimal("0"))
        orchard_total = sum((item.amount for item in related_costs), Decimal("0"))

        timeline: list[TimelineEvent] = []
        for activity in direct:
            timeline.append(
                TimelineEvent(
                    occurred_on=activity.performed_on,
                    kind="activity",
                    title=activity.activity_type.name,
                    subtitle=activity.description or activity.title,
                    amount=activity.total_cost,
                    currency=activity.currency,
                    scope_type=activity.scope_type,
                    activity_id=activity.id,
                    is_direct=True,
                )
            )
        for activity in related:
            scope_label = "Aktivnost reda" if activity.scope_type == ScopeType.ROW else "Aktivnost parcele"
            timeline.append(
                TimelineEvent(
                    occurred_on=activity.performed_on,
                    kind="activity",
                    title=activity.activity_type.name,
                    subtitle=f"{scope_label} · nije raspoređeno na ovo stablo",
                    amount=activity.total_cost,
                    currency=activity.currency,
                    scope_type=activity.scope_type,
                    activity_id=activity.id,
                    is_direct=False,
                )
            )
        for case in diseases:
            timeline.append(
                TimelineEvent(
                    occurred_on=case.detected_on,
                    kind="disease",
                    title=case.title,
                    subtitle=f"{case.category.value} · {case.severity.value} · {case.status.value}",
                    disease_id=case.id,
                    is_direct=True,
                )
            )
        for observation in observations:
            timeline.append(
                TimelineEvent(
                    occurred_on=observation.observed_on,
                    kind="observation",
                    title="Opažanje",
                    subtitle=observation.symptoms or observation.notes,
                    disease_id=observation.disease_case_id,
                    observation_id=observation.id,
                    is_direct=True,
                )
            )
        timeline.sort(key=lambda event: (event.occurred_on, event.title), reverse=True)

        return TreeJournalRead(
            tree=tree,
            timeline=timeline,
            activities=direct,
            related_activities=related,
            diseases=diseases,
            open_cases=open_cases,
            observations=observations,
            photos=photos,
            costs=direct_costs,
            related_costs=related_costs,
            direct_cost_total=direct_total,
            orchard_cost_total=orchard_total,
        )
