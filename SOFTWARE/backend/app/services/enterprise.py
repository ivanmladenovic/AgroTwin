"""Enterprise organization, assignments, read-only producer views, and planning."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import hash_password, verify_password
from app.enterprise.access import EnterpriseAccess
from app.models.enterprise import (
    EnterpriseMembership,
    EnterpriseOrganization,
    EnterpriseParcelAssignment,
    EnterprisePlanningSeason,
    EnterprisePurchase,
    EnterpriseSupplierLink,
    EnterpriseYieldPlan,
    EnterpriseYieldPlanItem,
)
from app.models.activity import Activity
from app.models.enums import (
    ActivitySemanticType,
    DiseaseCaseStatus,
    EnterpriseAuditAction,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseOrgStatus,
    EnterpriseRelationshipStatus,
    EnterpriseScenarioType,
    EnterpriseYieldPlanStatus,
    HealthStatus,
    ScopeType,
    TreeStatus,
)
from app.models.disease import DiseaseCase
from app.repositories.tree import TreeRepository
from app.models.farm import Farm
from app.models.harvest import HarvestEvent
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.models.user import User
from app.repositories.enterprise import EnterpriseRepository
from app.repositories.user import UserRepository
from app.schemas.enterprise import (
    EnterpriseActivityBrief,
    EnterpriseAggregateParcelSlice,
    EnterpriseAggregatePurchaseSlice,
    EnterpriseAggregatePurchaseSupplierRow,
    EnterpriseAggregateReport,
    EnterpriseAssignableParcel,
    EnterpriseDashboardKPIs,
    EnterpriseFarmCandidate,
    EnterpriseHarvestYearBrief,
    EnterpriseMapParcel,
    EnterpriseMembershipCreate,
    EnterpriseMembershipRead,
    EnterpriseMembershipUpdate,
    EnterpriseMeResponse,
    EnterpriseOrganizationRead,
    EnterpriseOrganizationUpdate,
    EnterpriseParcelAssignmentCreate,
    EnterpriseParcelAssignmentRead,
    EnterpriseParcelAssignmentUpdate,
    EnterpriseParcelDetail,
    EnterpriseParcelSummary,
    EnterprisePlanningSeasonCreate,
    EnterprisePlanningSeasonRead,
    EnterprisePlanningSeasonUpdate,
    EnterpriseProductionAnalytics,
    EnterprisePurchaseCurrency,
    EnterpriseQuantityBasis,
    EnterpriseSupplierLinkCreate,
    EnterpriseSupplierLinkRead,
    EnterpriseSupplierLinkUpdate,
    EnterpriseVarietyProductionRow,
    EnterpriseYearProductionRow,
    EnterpriseYieldComparison,
    EnterpriseYieldComparisonRow,
    EnterpriseYieldPlanCreate,
    EnterpriseYieldPlanItemRead,
    EnterpriseYieldPlanRead,
)
from app.schemas.orchard import OrchardTwinRead
from app.services.expected_yield_calc import compute_expected_yield
from app.services.orchard import OrchardService
from app.services.parcel_report_calc import mass_to_kg
from app.services.planting_resolution import planting_year_distribution
from app.yield_curve.expected_yield_profile import ExpectedYieldScenario

CALCULATION_VERSION = "enterprise-yield-v1"

SCENARIO_MAP = {
    EnterpriseScenarioType.CONSERVATIVE: ExpectedYieldScenario.PESSIMISTIC,
    EnterpriseScenarioType.REALISTIC: ExpectedYieldScenario.REALISTIC,
    EnterpriseScenarioType.OPTIMISTIC: ExpectedYieldScenario.OPTIMISTIC,
    EnterpriseScenarioType.CUSTOM: ExpectedYieldScenario.REALISTIC,
}


def _slugify(name: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base or f"enterprise-{uuid4().hex[:8]}"


class EnterpriseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EnterpriseRepository(db)
        self.access = EnterpriseAccess(db)
        self.users = UserRepository(db)

    # --- identity ---

    def me(self, user: User) -> EnterpriseMeResponse:
        memberships = self.repo.list_memberships_for_user(user.id)
        return EnterpriseMeResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            must_change_password=bool(user.must_change_password),
            memberships=[self._membership_read(item) for item in memberships],
        )

    def change_password(self, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.hashed_password):
            raise ForbiddenError("Trenutna lozinka nije ispravna")
        if len(new_password) < 8:
            raise ForbiddenError("Nova lozinka mora imati najmanje 8 karaktera")
        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        self.db.flush()
        return user

    # --- organization ---

    def get_organization(self, user: User, organization_id: UUID) -> EnterpriseOrganizationRead:
        self.access.require_reader(user, organization_id)
        org = self.access.require_org(organization_id)
        return EnterpriseOrganizationRead.model_validate(org)

    def update_organization(
        self, user: User, organization_id: UUID, payload: EnterpriseOrganizationUpdate
    ) -> EnterpriseOrganizationRead:
        self.access.require_admin(user, organization_id)
        org = self.access.require_org(organization_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(org, key, value)
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.ORG_UPDATED.value,
            entity_type="organization",
            entity_id=org.id,
            details={"fields": sorted(data.keys())},
        )
        self.db.flush()
        return EnterpriseOrganizationRead.model_validate(org)

    # --- memberships ---

    def list_memberships(self, user: User, organization_id: UUID) -> list[EnterpriseMembershipRead]:
        # Readers may see names so follow-up tasks can be assigned. Only admins can change membership.
        self.access.require_reader(user, organization_id)
        stmt = select(EnterpriseMembership).where(
            EnterpriseMembership.organization_id == organization_id
        )
        items = list(self.db.scalars(stmt).all())
        return [self._membership_read(item) for item in items]

    def add_membership(
        self, user: User, organization_id: UUID, payload: EnterpriseMembershipCreate
    ) -> EnterpriseMembershipRead:
        self.access.require_admin(user, organization_id)
        existing_user = self.users.get_by_email(payload.email)
        if existing_user is None:
            if not payload.temporary_password:
                raise ForbiddenError("Privremena lozinka je obavezna za novog korisnika")
            existing_user = User(
                email=payload.email.lower(),
                full_name=payload.full_name,
                hashed_password=hash_password(payload.temporary_password),
                is_active=True,
                is_superuser=False,
                must_change_password=True,
            )
            self.users.add(existing_user)
            self.db.flush()
        membership = self.repo.get_membership(organization_id, existing_user.id)
        if membership is None:
            membership = EnterpriseMembership(
                organization_id=organization_id,
                user_id=existing_user.id,
                role=payload.role,
                status=EnterpriseMembershipStatus.ACTIVE,
            )
            self.repo.add(membership)
        else:
            membership.role = payload.role
            membership.status = EnterpriseMembershipStatus.ACTIVE
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.MEMBER_ADDED.value,
            entity_type="membership",
            entity_id=membership.id,
            details={"role": payload.role.value, "email": payload.email},
        )
        self.db.flush()
        return self._membership_read(membership)

    def update_membership(
        self,
        user: User,
        organization_id: UUID,
        membership_id: UUID,
        payload: EnterpriseMembershipUpdate,
    ) -> EnterpriseMembershipRead:
        self.access.require_admin(user, organization_id)
        membership = self.db.get(EnterpriseMembership, membership_id)
        if membership is None or membership.organization_id != organization_id:
            raise NotFoundError("Članstvo nije pronađeno")
        data = payload.model_dump(exclude_unset=True)
        new_status = data.get("status")
        if (
            new_status == EnterpriseMembershipStatus.INACTIVE
            and membership.user_id == user.id
            and membership.role == EnterpriseMembershipRole.ENTERPRISE_ADMIN
            and membership.status == EnterpriseMembershipStatus.ACTIVE
        ):
            other_admins = self.db.scalar(
                select(func.count())
                .select_from(EnterpriseMembership)
                .where(
                    EnterpriseMembership.organization_id == organization_id,
                    EnterpriseMembership.status == EnterpriseMembershipStatus.ACTIVE,
                    EnterpriseMembership.role == EnterpriseMembershipRole.ENTERPRISE_ADMIN,
                    EnterpriseMembership.id != membership.id,
                )
            )
            if not other_admins:
                raise ForbiddenError(
                    "Poslednji administrator ne može da deaktivira sopstveno članstvo"
                )
        for key, value in data.items():
            setattr(membership, key, value)
        safe_details = {
            key: value.value if hasattr(value, "value") else value for key, value in data.items()
        }
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.MEMBER_UPDATED.value,
            entity_type="membership",
            entity_id=membership.id,
            details=safe_details,
        )
        self.db.flush()
        return self._membership_read(membership)

    # --- suppliers ---

    def list_suppliers(
        self, user: User, organization_id: UUID, *, status: str | None = None, q: str | None = None
    ) -> list[EnterpriseSupplierLinkRead]:
        self.access.require_reader(user, organization_id)
        links = self.repo.list_supplier_links(organization_id)
        results: list[EnterpriseSupplierLinkRead] = []
        for link in links:
            if status and link.status.value != status:
                continue
            farm = link.farm
            if q:
                needle = q.lower()
                display, owner_name, public = self._producer_display(farm)
                hay = " ".join(
                    filter(
                        None,
                        [
                            display,
                            owner_name,
                            public,
                            farm.name if farm else None,
                            link.internal_code,
                        ],
                    )
                ).lower()
                if needle not in hay:
                    continue
            results.append(self._supplier_read(organization_id, link))
        return results

    def get_supplier(
        self, user: User, organization_id: UUID, link_id: UUID
    ) -> EnterpriseSupplierLinkRead:
        self.access.require_reader(user, organization_id)
        link = self.repo.get_supplier_link(organization_id, link_id)
        if link is None:
            raise NotFoundError("Dobavljač nije pronađen")
        return self._supplier_read(organization_id, link)

    def create_supplier(
        self, user: User, organization_id: UUID, payload: EnterpriseSupplierLinkCreate
    ) -> EnterpriseSupplierLinkRead:
        self.access.require_admin(user, organization_id)
        farm = self.repo.get_farm(payload.farm_id)
        if farm is None:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        existing = self.repo.get_supplier_by_farm(organization_id, payload.farm_id)
        if existing is not None:
            raise ForbiddenError("Dobavljač je već povezan sa organizacijom")
        link = EnterpriseSupplierLink(
            organization_id=organization_id,
            farm_id=payload.farm_id,
            status=payload.status,
            relationship_start=payload.relationship_start,
            relationship_end=payload.relationship_end,
            internal_code=payload.internal_code,
            internal_group=payload.internal_group,
            internal_notes=payload.internal_notes,
            assigned_by_id=user.id,
        )
        self.repo.add(link)
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.SUPPLIER_ASSIGNED.value,
            entity_type="supplier_link",
            entity_id=link.id,
            details={"farm_id": str(payload.farm_id)},
        )
        self.db.flush()
        link = self.repo.get_supplier_link(organization_id, link.id)
        assert link is not None
        return self._supplier_read(organization_id, link)

    def update_supplier(
        self,
        user: User,
        organization_id: UUID,
        link_id: UUID,
        payload: EnterpriseSupplierLinkUpdate,
    ) -> EnterpriseSupplierLinkRead:
        self.access.require_admin(user, organization_id)
        link = self.repo.get_supplier_link(organization_id, link_id)
        if link is None:
            raise NotFoundError("Dobavljač nije pronađen")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(link, key, value)
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.SUPPLIER_UPDATED.value,
            entity_type="supplier_link",
            entity_id=link.id,
            details={"fields": sorted(data.keys())},
        )
        self.db.flush()
        return self._supplier_read(organization_id, link)

    # --- parcel assignments ---

    def list_assignments(
        self, user: User, organization_id: UUID
    ) -> list[EnterpriseParcelAssignmentRead]:
        self.access.require_reader(user, organization_id)
        return [
            self._assignment_read(item)
            for item in self.repo.list_parcel_assignments(organization_id)
        ]

    def assign_parcel(
        self, user: User, organization_id: UUID, payload: EnterpriseParcelAssignmentCreate
    ) -> EnterpriseParcelAssignmentRead:
        self.access.require_admin(user, organization_id)
        parcel = self.repo.get_parcel(payload.parcel_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        # Supplier link is required before parcel assignment (explicit network membership).
        self.access.require_supplier_link(organization_id, parcel.farm_id)
        existing = self.repo.get_assignment_by_parcel(organization_id, payload.parcel_id)
        if existing is not None:
            raise ForbiddenError("Parcela je već dodeljena organizaciji")
        assignment = EnterpriseParcelAssignment(
            organization_id=organization_id,
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            status=payload.status,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            assigned_by_id=user.id,
        )
        self.repo.add(assignment)
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.PARCEL_ASSIGNED.value,
            entity_type="parcel_assignment",
            entity_id=assignment.id,
            details={"parcel_id": str(parcel.id), "farm_id": str(parcel.farm_id)},
        )
        self.db.flush()
        loaded = self.repo.get_parcel_assignment(organization_id, assignment.id)
        assert loaded is not None
        return self._assignment_read(loaded)

    def update_assignment(
        self,
        user: User,
        organization_id: UUID,
        assignment_id: UUID,
        payload: EnterpriseParcelAssignmentUpdate,
    ) -> EnterpriseParcelAssignmentRead:
        self.access.require_admin(user, organization_id)
        assignment = self.repo.get_parcel_assignment(organization_id, assignment_id)
        if assignment is None:
            raise NotFoundError("Dodeljena parcela nije pronađena")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(assignment, key, value)
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.PARCEL_UPDATED.value,
            entity_type="parcel_assignment",
            entity_id=assignment.id,
            details={"fields": sorted(data.keys())},
        )
        self.db.flush()
        return self._assignment_read(assignment)

    # --- read-only parcels ---

    def list_parcels(
        self,
        user: User,
        organization_id: UUID,
        *,
        farm_id: UUID | None = None,
        q: str | None = None,
    ) -> list[EnterpriseParcelSummary]:
        self.access.require_reader(user, organization_id)
        parcel_ids = self.access.assigned_parcel_ids(organization_id)
        if not parcel_ids:
            return []
        stmt = (
            select(Parcel)
            .where(Parcel.id.in_(parcel_ids))
            .order_by(Parcel.name.asc())
        )
        parcels = list(self.db.scalars(stmt).all())
        results: list[EnterpriseParcelSummary] = []
        for parcel in parcels:
            if farm_id and parcel.farm_id != farm_id:
                continue
            farm = self.repo.get_farm(parcel.farm_id)
            if q:
                needle = q.lower()
                display, _, _ = self._producer_display(farm)
                hay = f"{parcel.name} {farm.name if farm else ''} {display or ''}".lower()
                if needle not in hay:
                    continue
            results.append(self._parcel_summary(parcel, farm))
        return results

    def get_parcel_detail(
        self, user: User, organization_id: UUID, parcel_id: UUID
    ) -> EnterpriseParcelDetail:
        self.access.require_reader(user, organization_id)
        self.access.require_parcel_read(organization_id, parcel_id)
        parcel = self.repo.get_parcel(parcel_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        farm = self.repo.get_farm(parcel.farm_id)
        summary = self._parcel_summary(parcel, farm)
        planting_years = self._planting_year_distribution(parcel.id)
        harvest_years = self._harvest_years(parcel.id)
        harvest_by_year = self._harvest_by_year(parcel.id)
        activities = self._recent_activities(parcel.id, limit=12)
        activity_counts = self._activity_counts(parcel.id)
        return EnterpriseParcelDetail(
            **summary.model_dump(),
            boundary=parcel.boundary,
            maps_url=parcel.maps_url,
            row_count=parcel.row_count,
            trees_per_row=parcel.trees_per_row,
            planting_year_distribution={str(k): v for k, v in planting_years.items()},
            harvest_years=harvest_years,
            harvest_by_year=harvest_by_year,
            recent_activities=activities,
            activity_counts=activity_counts,
            protection_count=activity_counts.get(ActivitySemanticType.TREATMENT.value, 0),
            fertilization_count=activity_counts.get(
                ActivitySemanticType.FERTILIZATION.value, 0
            ),
            irrigation_count=activity_counts.get(ActivitySemanticType.IRRIGATION.value, 0),
            observation_count=activity_counts.get(ActivitySemanticType.OBSERVATION.value, 0)
            + activity_counts.get(ActivitySemanticType.PROBLEM.value, 0),
        )

    def map_parcels(
        self, user: User, organization_id: UUID
    ) -> list[EnterpriseMapParcel]:
        self.access.require_reader(user, organization_id)
        parcels = self.list_parcels(user, organization_id)
        trees = TreeRepository(self.db)
        results: list[EnterpriseMapParcel] = []
        for parcel in parcels:
            if parcel.latitude is None or parcel.longitude is None:
                continue
            health = trees.health_counts(parcel.parcel_id)
            open_cases = int(
                self.db.scalar(
                    select(func.count())
                    .select_from(DiseaseCase)
                    .where(
                        DiseaseCase.parcel_id == parcel.parcel_id,
                        DiseaseCase.status != DiseaseCaseStatus.RESOLVED,
                    )
                )
                or 0
            )
            results.append(
                EnterpriseMapParcel(
                    parcel_id=parcel.parcel_id,
                    parcel_name=parcel.parcel_name,
                    producer_display_name=parcel.producer_display_name,
                    latitude=float(parcel.latitude),
                    longitude=float(parcel.longitude),
                    area_hectares=parcel.area_hectares,
                    tree_count=parcel.tree_count,
                    completeness_score=parcel.completeness_score,
                    issue_trees=int(health.get(HealthStatus.ISSUE, 0) or 0),
                    monitoring_trees=int(health.get(HealthStatus.MONITORING, 0) or 0),
                    healthy_trees=int(health.get(HealthStatus.HEALTHY, 0) or 0),
                    open_cases=open_cases,
                )
            )
        return results

    def production_analytics(
        self,
        user: User,
        organization_id: UUID,
        *,
        years_back: int = 5,
        reference_year: int | None = None,
        parcel_ids: list[UUID] | None = None,
    ) -> EnterpriseProductionAnalytics:
        self.access.require_reader(user, organization_id)
        assigned_ids = set(self.access.assigned_parcel_ids(organization_id))
        notes: list[str] = []
        if not assigned_ids:
            notes.append("Nema dodeljenih parcela za analitiku.")
            return EnterpriseProductionAnalytics(notes=notes)

        if parcel_ids is not None:
            selected = [pid for pid in parcel_ids if pid in assigned_ids]
            if not selected:
                notes.append("Nijedna odabrana parcela nije dostupna organizaciji.")
                return EnterpriseProductionAnalytics(notes=notes)
            parcel_ids = selected
        else:
            parcel_ids = list(assigned_ids)

        current = reference_year or date.today().year
        year_rows: list[EnterpriseYearProductionRow] = []
        parcels = list(self.db.scalars(select(Parcel).where(Parcel.id.in_(parcel_ids))).all())
        assigned = len(parcels)

        for year in range(current - years_back + 1, current + 1):
            expected_sum = Decimal("0")
            has_expected = False
            for parcel in parcels:
                value = self._expected_for_parcel(parcel, year)
                if value is not None:
                    expected_sum += value
                    has_expected = True
            actual, _event_count, parcels_with_set = self._parcel_harvest_net_kg(parcel_ids, year)
            year_rows.append(
                EnterpriseYearProductionRow(
                    year=year,
                    expected_yield_kg=expected_sum if has_expected else None,
                    actual_yield_kg=actual,
                    parcels_with_harvest=len(parcels_with_set),
                    assigned_parcels=assigned,
                )
            )

        variety_tree_counts: Counter[str] = Counter()
        variety_expected: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        variety_has_expected: set[str] = set()
        for parcel in parcels:
            rows, trees = self._parcel_rows_trees(parcel)
            rows_by_id = {row.id: row for row in rows}
            by_variety_trees: dict[str, list[Tree]] = defaultdict(list)
            for tree in trees:
                by_variety_trees[self._tree_variety_label(tree, parcel, rows_by_id)].append(tree)
            for variety, var_trees in by_variety_trees.items():
                variety_tree_counts[variety] += len(var_trees)
                distribution, unknown = planting_year_distribution(
                    parcel=parcel, rows=rows, trees=var_trees
                )
                totals = compute_expected_yield(
                    distribution=distribution,
                    unknown_tree_count=unknown,
                    reference_year=current,
                    area_hectares=None,
                )
                if totals.available and totals.realistic_kg is not None:
                    variety_expected[variety] += totals.realistic_kg
                    variety_has_expected.add(variety)

        total_trees = sum(variety_tree_counts.values())
        actual_total, _, _ = self._parcel_harvest_net_kg(parcel_ids, current)
        variety_rows: list[EnterpriseVarietyProductionRow] = []
        for variety, count in variety_tree_counts.most_common():
            share = (100.0 * count / total_trees) if total_trees else None
            expected_v = (
                variety_expected[variety].quantize(Decimal("0.001"))
                if variety in variety_has_expected
                else None
            )
            actual_v = None
            if share is not None and actual_total is not None and total_trees:
                actual_v = (actual_total * Decimal(str(count)) / Decimal(str(total_trees))).quantize(
                    Decimal("0.001")
                )
            variety_rows.append(
                EnterpriseVarietyProductionRow(
                    variety=variety,
                    tree_count=count,
                    expected_yield_kg=expected_v,
                    actual_yield_kg=actual_v,
                    share_of_trees_percent=round(share, 1) if share is not None else None,
                )
            )
        notes.append(
            "Očekivano je bruto (kg ploda u ljusci), isto kao na klijentskom nalogu; ostvareno je neto berba na nivou parcele."
        )
        if variety_rows and actual_total is not None:
            notes.append(
                "Ostvareno po sortama je procena proporcionalna broju stabala — berba nije vođena po sorti."
            )

        return EnterpriseProductionAnalytics(
            by_year=year_rows,
            by_variety=variety_rows,
            notes=notes,
        )

    def aggregate_report(
        self,
        user: User,
        organization_id: UUID,
        *,
        parcel_ids: list[UUID],
        year: int | None = None,
    ) -> EnterpriseAggregateReport:
        self.access.require_reader(user, organization_id)
        org = self.repo.get_org(organization_id)
        if org is None:
            raise NotFoundError("Organizacija nije pronađena")
        season_year = year or date.today().year
        assigned = set(self.access.assigned_parcel_ids(organization_id))
        selected = [pid for pid in parcel_ids if pid in assigned]
        if not selected:
            raise NotFoundError("Nijedna odabrana parcela nije dostupna organizaciji")

        notes: list[str] = []
        parcels = list(self.db.scalars(select(Parcel).where(Parcel.id.in_(selected))).all())
        slices: list[EnterpriseAggregateParcelSlice] = []
        total_area = Decimal("0")
        has_area = False
        total_trees = 0
        expected_sum = Decimal("0")
        has_expected = False
        actual_sum = Decimal("0")
        parcels_with_harvest = 0

        for parcel in parcels:
            farm = self.repo.get_farm(parcel.farm_id)
            summary = self._parcel_summary(parcel, farm)
            expected = self._expected_for_parcel(parcel, season_year)
            actual, _count, _parcels = self._parcel_harvest_net_kg([parcel.id], season_year)
            has_harvest = actual is not None
            activity_count = int(
                self.db.scalar(
                    select(func.count())
                    .select_from(Activity)
                    .where(
                        Activity.parcel_id == parcel.id,
                        extract("year", Activity.performed_on) == season_year,
                    )
                )
                or 0
            )
            if summary.area_hectares is not None:
                total_area += summary.area_hectares
                has_area = True
            total_trees += summary.tree_count
            if expected is not None:
                expected_sum += expected
                has_expected = True
            if has_harvest:
                actual_sum += Decimal(str(actual or 0))
                parcels_with_harvest += 1

            slices.append(
                EnterpriseAggregateParcelSlice(
                    parcel_id=parcel.id,
                    parcel_name=parcel.name,
                    producer_display_name=summary.producer_display_name,
                    area_hectares=summary.area_hectares,
                    tree_count=summary.tree_count,
                    variety_names=summary.variety_names,
                    expected_yield_kg=expected,
                    actual_yield_kg=Decimal(str(actual or 0)) if has_harvest else None,
                    activity_count=activity_count if activity_count > 0 else None,
                    completeness_score=summary.completeness_score,
                )
            )

        coverage = None
        if parcels:
            coverage = round(100.0 * parcels_with_harvest / len(parcels), 1)
            if parcels_with_harvest < len(parcels):
                notes.append(
                    "Pokriće berbe računa samo parcele sa evidentiranom berbom; nedostajuća berba nije nula."
                )

        # Realized purchases (otkup) for suppliers of selected parcels.
        farm_ids = sorted({parcel.farm_id for parcel in parcels})
        purchase_slices: list[EnterpriseAggregatePurchaseSlice] = []
        purchase_supplier_rows: list[EnterpriseAggregatePurchaseSupplierRow] = []
        purchase_totals_by_currency: dict[str, Decimal] = {}
        purchased_quantity: Decimal | None = None
        purchase_count = 0
        if farm_ids:
            purchase_rows = list(
                self.db.scalars(
                    select(EnterprisePurchase)
                    .where(
                        EnterprisePurchase.organization_id == organization_id,
                        EnterprisePurchase.farm_id.in_(farm_ids),
                        extract("year", EnterprisePurchase.purchased_on) == season_year,
                    )
                    .order_by(
                        EnterprisePurchase.purchased_on.desc(),
                        EnterprisePurchase.created_at.desc(),
                    )
                ).all()
            )
            purchase_count = len(purchase_rows)
            qty_sum = Decimal("0")
            by_supplier: dict[UUID, dict] = {}
            for row in purchase_rows:
                farm = self.repo.get_farm(row.farm_id)
                display, _, _ = self._producer_display(farm)
                purchase_slices.append(
                    EnterpriseAggregatePurchaseSlice(
                        purchase_id=row.id,
                        farm_id=row.farm_id,
                        producer_display_name=display,
                        farm_name=farm.name if farm else None,
                        purchased_on=row.purchased_on,
                        quantity_kg=row.quantity_kg,
                        quantity_basis=EnterpriseQuantityBasis(row.quantity_basis),
                        currency=EnterprisePurchaseCurrency(row.currency),
                        unit_price_per_kg=row.unit_price_per_kg,
                        total_amount=row.total_amount,
                        notes=row.notes,
                    )
                )
                qty_sum += row.quantity_kg
                cur = str(row.currency)
                purchase_totals_by_currency[cur] = (
                    purchase_totals_by_currency.get(cur, Decimal("0")) + row.total_amount
                )
                bucket = by_supplier.setdefault(
                    row.farm_id,
                    {
                        "display": display,
                        "farm_name": farm.name if farm else None,
                        "count": 0,
                        "qty": Decimal("0"),
                        "amounts": {},
                    },
                )
                bucket["count"] += 1
                bucket["qty"] += row.quantity_kg
                bucket["amounts"][cur] = bucket["amounts"].get(cur, Decimal("0")) + row.total_amount

            if purchase_count:
                purchased_quantity = qty_sum
                purchase_supplier_rows = [
                    EnterpriseAggregatePurchaseSupplierRow(
                        farm_id=farm_id,
                        producer_display_name=data["display"],
                        farm_name=data["farm_name"],
                        purchase_count=data["count"],
                        quantity_kg=data["qty"],
                        amount_by_currency=data["amounts"],
                    )
                    for farm_id, data in sorted(
                        by_supplier.items(),
                        key=lambda item: (item[1]["display"] or item[1]["farm_name"] or "").lower(),
                    )
                ]
            else:
                notes.append(
                    f"Nema evidentiranih otkupa za {season_year} kod dobavljača odabranih parcela."
                )

        return EnterpriseAggregateReport(
            organization_name=org.name,
            year=season_year,
            generated_on=date.today(),
            parcel_count=len(parcels),
            total_area_ha=total_area if has_area else None,
            total_trees=total_trees if total_trees > 0 else None,
            expected_yield_kg=expected_sum if has_expected else None,
            actual_yield_kg=actual_sum if parcels_with_harvest > 0 else None,
            harvest_coverage_percent=coverage,
            parcels=slices,
            purchase_count=purchase_count,
            purchased_quantity_kg=purchased_quantity,
            purchase_totals_by_currency=purchase_totals_by_currency,
            purchases=purchase_slices,
            purchases_by_supplier=purchase_supplier_rows,
            notes=notes,
        )

    # --- dashboard ---

    def dashboard(
        self, user: User, organization_id: UUID, *, year: int | None = None
    ) -> EnterpriseDashboardKPIs:
        self.access.require_reader(user, organization_id)
        season_year = year or date.today().year
        parcel_ids = self.access.assigned_parcel_ids(organization_id)
        farm_ids = self.access.assigned_farm_ids(organization_id)
        notes: list[str] = []

        active_suppliers = len(
            [
                link
                for link in self.repo.list_supplier_links(organization_id)
                if link.status == EnterpriseRelationshipStatus.ACTIVE
            ]
        )

        total_area: Decimal | None = None
        total_trees = 0
        missing_key = 0
        if parcel_ids:
            area_stmt = select(func.coalesce(func.sum(Parcel.area_hectares), 0)).where(
                Parcel.id.in_(parcel_ids)
            )
            total_area = Decimal(str(self.db.scalar(area_stmt) or 0))
            tree_stmt = (
                select(func.count())
                .select_from(Tree)
                .where(Tree.parcel_id.in_(parcel_ids), Tree.status == TreeStatus.ACTIVE)
            )
            total_trees = int(self.db.scalar(tree_stmt) or 0)
            parcels = list(self.db.scalars(select(Parcel).where(Parcel.id.in_(parcel_ids))).all())
            for parcel in parcels:
                missing = self._missing_fields(parcel)
                if missing:
                    missing_key += 1
        else:
            notes.append("Nema dodeljenih parcela — KPI su ograničeni.")

        expected_total: Decimal | None = None
        actual_total: Decimal | None = None
        coverage: float | None = None
        if parcel_ids:
            expected_sum = Decimal("0")
            parcels = list(self.db.scalars(select(Parcel).where(Parcel.id.in_(parcel_ids))).all())
            for parcel in parcels:
                value = self._expected_for_parcel(parcel, season_year)
                if value is not None:
                    expected_sum += value
            expected_total = expected_sum if expected_sum > 0 else None

            # Missing harvest is not treated as zero production for coverage.
            actual_total, _event_count, parcels_with_set = self._parcel_harvest_net_kg(
                parcel_ids, season_year
            )
            if actual_total is None:
                notes.append(
                    f"Nema evidentirane berbe za {season_year}. — ostvareni prinos nije dostupan."
                )
            parcels_with_harvest = len(parcels_with_set)
            if parcel_ids:
                coverage = round(100.0 * parcels_with_harvest / len(parcel_ids), 1)

        return EnterpriseDashboardKPIs(
            active_suppliers=active_suppliers,
            assigned_farms=len(farm_ids),
            assigned_parcels=len(parcel_ids),
            total_area_ha=total_area,
            total_trees=total_trees if parcel_ids else None,
            expected_yield_kg=expected_total,
            actual_yield_kg=actual_total,
            harvest_coverage_percent=coverage,
            parcels_missing_key_data=missing_key,
            parcels_with_issues=self._parcels_with_issues_count(organization_id),
            season_year=season_year,
            notes=notes,
        )

    def _parcels_with_issues_count(self, organization_id: UUID) -> int:
        from app.services.enterprise_monitoring import EnterpriseMonitoringService

        return EnterpriseMonitoringService(self.db).count_parcels_with_issues(organization_id)

    def monitoring_center(
        self,
        user: User,
        organization_id: UUID,
        *,
        year: int | None = None,
        farm_id: UUID | None = None,
        parcel_id: UUID | None = None,
        category: str | None = None,
        review_status: str | None = None,
        severity: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        from app.services.enterprise_monitoring import EnterpriseMonitoringService

        return EnterpriseMonitoringService(self.db).monitoring_center(
            user,
            organization_id,
            year=year,
            farm_id=farm_id,
            parcel_id=parcel_id,
            category=category,
            review_status=review_status,
            severity=severity,
            date_from=date_from,
            date_to=date_to,
        )

    # --- planning seasons / yield plans ---

    def list_seasons(self, user: User, organization_id: UUID) -> list[EnterprisePlanningSeasonRead]:
        self.access.require_reader(user, organization_id)
        return [
            EnterprisePlanningSeasonRead.model_validate(item)
            for item in self.repo.list_seasons(organization_id)
        ]

    def create_season(
        self, user: User, organization_id: UUID, payload: EnterprisePlanningSeasonCreate
    ) -> EnterprisePlanningSeasonRead:
        self.access.require_plan_writer(user, organization_id)
        if self.repo.get_season_by_year(organization_id, payload.year):
            raise ForbiddenError(f"Sezona {payload.year} već postoji")
        season = EnterprisePlanningSeason(
            organization_id=organization_id,
            year=payload.year,
            name=payload.name,
            status=payload.status,
            supply_target_kg=payload.supply_target_kg,
        )
        self.repo.add(season)
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.SEASON_CREATED.value,
            entity_type="planning_season",
            entity_id=season.id,
            details={"year": payload.year},
        )
        self.db.flush()
        return EnterprisePlanningSeasonRead.model_validate(season)

    def update_season(
        self,
        user: User,
        organization_id: UUID,
        season_id: UUID,
        payload: EnterprisePlanningSeasonUpdate,
    ) -> EnterprisePlanningSeasonRead:
        self.access.require_plan_writer(user, organization_id)
        season = self.repo.get_season(organization_id, season_id)
        if season is None:
            raise NotFoundError("Sezona nije pronađena")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(season, key, value)
        self.db.flush()
        return EnterprisePlanningSeasonRead.model_validate(season)

    def list_yield_plans(
        self, user: User, organization_id: UUID, season_id: UUID | None = None
    ) -> list[EnterpriseYieldPlanRead]:
        self.access.require_reader(user, organization_id)
        return [
            self._plan_read(plan) for plan in self.repo.list_yield_plans(organization_id, season_id)
        ]

    def get_yield_plan(
        self, user: User, organization_id: UUID, plan_id: UUID
    ) -> EnterpriseYieldPlanRead:
        self.access.require_reader(user, organization_id)
        plan = self.repo.get_yield_plan(organization_id, plan_id)
        if plan is None:
            raise NotFoundError("Plan prinosa nije pronađen")
        return self._plan_read(plan)

    def create_yield_plan(
        self, user: User, organization_id: UUID, payload: EnterpriseYieldPlanCreate
    ) -> EnterpriseYieldPlanRead:
        self.access.require_plan_writer(user, organization_id)
        season = self.repo.get_season(organization_id, payload.planning_season_id)
        if season is None:
            raise NotFoundError("Sezona nije pronađena")
        assigned = self.access.assigned_parcel_ids(organization_id)
        selected = set(payload.parcel_ids) if payload.parcel_ids else assigned
        unauthorized = selected - assigned
        if unauthorized:
            raise ForbiddenError("Plan sadrži parcele koje nisu dodeljene organizaciji")
        if not selected:
            raise ForbiddenError("Nema parcela za izradu plana")

        plan = EnterpriseYieldPlan(
            organization_id=organization_id,
            planning_season_id=season.id,
            name=payload.name,
            description=payload.description,
            scenario_type=payload.scenario_type,
            status=EnterpriseYieldPlanStatus.DRAFT,
            assumptions=payload.assumptions or {},
            calculation_version=CALCULATION_VERSION,
            created_by_id=user.id,
        )
        self.repo.add(plan)
        self.db.flush()

        curve_scenario = SCENARIO_MAP[payload.scenario_type]
        for parcel_id in sorted(selected, key=str):
            parcel = self.repo.get_parcel(parcel_id)
            if parcel is None:
                continue
            item = self._build_plan_item(plan, parcel, season.year, curve_scenario, payload.assumptions)
            self.repo.add(item)

        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.PLAN_CREATED.value,
            entity_type="yield_plan",
            entity_id=plan.id,
            details={
                "scenario": payload.scenario_type.value,
                "season_year": season.year,
                "parcel_count": len(selected),
            },
        )
        self.db.flush()
        loaded = self.repo.get_yield_plan(organization_id, plan.id)
        assert loaded is not None
        return self._plan_read(loaded)

    def recalculate_yield_plan(
        self, user: User, organization_id: UUID, plan_id: UUID
    ) -> EnterpriseYieldPlanRead:
        """Create a new plan version with the same settings; preserve the prior plan."""
        self.access.require_plan_writer(user, organization_id)
        source = self.repo.get_yield_plan(organization_id, plan_id)
        if source is None:
            raise NotFoundError("Plan prinosa nije pronađen")
        season = self.repo.get_season(organization_id, source.planning_season_id)
        if season is None:
            raise NotFoundError("Sezona nije pronađena")
        parcel_ids = [item.parcel_id for item in source.items]
        created = self.create_yield_plan(
            user,
            organization_id,
            EnterpriseYieldPlanCreate(
                planning_season_id=source.planning_season_id,
                name=f"{source.name} (rekalkulacija)",
                description=source.description,
                scenario_type=source.scenario_type,
                assumptions={
                    **(source.assumptions or {}),
                    "recalculated_from_plan_id": str(source.id),
                },
                parcel_ids=parcel_ids,
            ),
        )
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.PLAN_RECALCULATED.value,
            entity_type="yield_plan",
            entity_id=created.id,
            details={"from_plan_id": str(source.id)},
        )
        self.db.flush()
        return created

    # --- helpers ---

    def _membership_read(self, membership: EnterpriseMembership) -> EnterpriseMembershipRead:
        user = self.db.get(User, membership.user_id)
        org = membership.organization or self.db.get(EnterpriseOrganization, membership.organization_id)
        return EnterpriseMembershipRead(
            id=membership.id,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            role=membership.role,
            status=membership.status,
            organization=EnterpriseOrganizationRead.model_validate(org) if org else None,
            user_email=user.email if user else None,
            user_full_name=user.full_name if user else None,
        )

    def _producer_display(self, farm: Farm | None) -> tuple[str | None, str | None, str | None]:
        """Return (display_name, owner_full_name, public_producer_name)."""
        if farm is None:
            return None, None, None
        public = (farm.public_producer_name or "").strip() or None
        owner = self.db.get(User, farm.owner_id) if farm.owner_id else None
        owner_name = (owner.full_name or "").strip() if owner else None
        display = public or owner_name or farm.name
        return display, owner_name, public

    def _variety_names(self, parcel: Parcel) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        def add(value: str | None) -> None:
            text = (value or "").strip()
            key = text.casefold()
            if not text or key in seen:
                return
            seen.add(key)
            names.append(text)

        raw = parcel.varieties or []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    add(str(item.get("name") or ""))
                elif isinstance(item, str):
                    add(item)
        add(parcel.default_variety)
        return names

    def _supplier_read(
        self, organization_id: UUID, link: EnterpriseSupplierLink
    ) -> EnterpriseSupplierLinkRead:
        farm = link.farm or self.repo.get_farm(link.farm_id)
        display, owner_name, public = self._producer_display(farm)
        season_year = date.today().year
        expected: Decimal | None = None
        actual: Decimal | None = None
        completeness_vals: list[float] = []

        assigned_ids = self.access.assigned_parcel_ids(organization_id)
        farm_parcel_ids: list[UUID] = []
        if assigned_ids:
            farm_parcel_ids = list(
                self.db.scalars(
                    select(Parcel.id).where(
                        Parcel.farm_id == link.farm_id,
                        Parcel.id.in_(assigned_ids),
                    )
                ).all()
            )

        if farm_parcel_ids:
            for parcel in self.db.scalars(
                select(Parcel).where(Parcel.id.in_(farm_parcel_ids))
            ).all():
                summary = self._parcel_summary(parcel, farm)
                if summary.completeness_score is not None:
                    completeness_vals.append(summary.completeness_score)
                value = self._expected_for_parcel(parcel, season_year)
                if value is not None:
                    expected = (expected or Decimal("0")) + value

            actual, _count, _parcels = self._parcel_harvest_net_kg(farm_parcel_ids, season_year)

        return EnterpriseSupplierLinkRead(
            id=link.id,
            created_at=link.created_at,
            updated_at=link.updated_at,
            organization_id=link.organization_id,
            farm_id=link.farm_id,
            status=link.status,
            relationship_start=link.relationship_start,
            relationship_end=link.relationship_end,
            internal_code=link.internal_code,
            internal_group=link.internal_group,
            internal_notes=link.internal_notes,
            assigned_at=link.assigned_at,
            farm_name=farm.name if farm else None,
            farm_location=farm.location_name if farm else None,
            producer_display_name=display,
            owner_full_name=owner_name,
            public_producer_name=public,
            assigned_parcel_count=self.repo.count_active_assignments_for_farm(
                organization_id, link.farm_id
            ),
            assigned_area_ha=self.repo.sum_assigned_area_for_farm(organization_id, link.farm_id),
            expected_yield_kg=expected,
            actual_yield_kg=actual,
            completeness_avg=(
                round(sum(completeness_vals) / len(completeness_vals), 1)
                if completeness_vals
                else None
            ),
        )

    def _assignment_read(self, item: EnterpriseParcelAssignment) -> EnterpriseParcelAssignmentRead:
        parcel = item.parcel
        farm = item.farm
        return EnterpriseParcelAssignmentRead(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            organization_id=item.organization_id,
            farm_id=item.farm_id,
            parcel_id=item.parcel_id,
            status=item.status,
            valid_from=item.valid_from,
            valid_until=item.valid_until,
            assigned_at=item.assigned_at,
            parcel_name=parcel.name if parcel else None,
            farm_name=farm.name if farm else None,
            area_hectares=parcel.area_hectares if parcel else None,
        )

    def _missing_fields(self, parcel: Parcel) -> list[str]:
        missing: list[str] = []
        if parcel.area_hectares is None:
            missing.append("area_hectares")
        if parcel.boundary is None:
            missing.append("boundary")
        if not parcel.default_variety and not parcel.varieties:
            missing.append("variety")
        if parcel.default_planting_year is None:
            missing.append("planting_year")
        if self.repo.tree_count(parcel.id) == 0:
            missing.append("trees")
        return missing

    def _parcel_summary(self, parcel: Parcel, farm: Farm | None) -> EnterpriseParcelSummary:
        missing = self._missing_fields(parcel)
        required = ["area_hectares", "variety", "planting_year", "trees"]
        present = len(required) - len([f for f in missing if f in required])
        score = round(100.0 * present / len(required), 1)
        display, _, _ = self._producer_display(farm)
        variety_names = self._variety_names(parcel)
        return EnterpriseParcelSummary(
            parcel_id=parcel.id,
            farm_id=parcel.farm_id,
            parcel_name=parcel.name,
            farm_name=farm.name if farm else "—",
            producer_display_name=display,
            area_hectares=parcel.area_hectares,
            tree_count=self.repo.tree_count(parcel.id),
            default_variety=parcel.default_variety,
            varieties=list(parcel.varieties or []),
            variety_names=variety_names,
            default_planting_year=parcel.default_planting_year,
            latitude=parcel.latitude,
            longitude=parcel.longitude,
            has_boundary=parcel.boundary is not None,
            completeness_score=score,
            missing_fields=missing,
            expected_yield_kg=self._expected_for_parcel(parcel, date.today().year),
            latest_harvest_kg=self._latest_harvest_kg(parcel.id),
        )

    def _harvest_by_year(self, parcel_id: UUID) -> list[EnterpriseHarvestYearBrief]:
        years = self._harvest_years(parcel_id)
        rows: list[EnterpriseHarvestYearBrief] = []
        for year in years:
            net_kg, event_count, _parcels = self._parcel_harvest_net_kg([parcel_id], year)
            if net_kg is None:
                continue
            rows.append(
                EnterpriseHarvestYearBrief(
                    year=year,
                    net_kg=net_kg,
                    event_count=event_count,
                )
            )
        return rows

    def _recent_activities(
        self, parcel_id: UUID, *, limit: int = 12
    ) -> list[EnterpriseActivityBrief]:
        stmt = (
            select(Activity)
            .where(Activity.parcel_id == parcel_id)
            .order_by(Activity.performed_on.desc(), Activity.created_at.desc())
            .limit(limit)
        )
        results: list[EnterpriseActivityBrief] = []
        for activity in self.db.scalars(stmt).all():
            type_name = None
            if activity.activity_type is not None:
                type_name = activity.activity_type.name
            semantic = (
                activity.semantic_type.value
                if activity.semantic_type is not None
                else None
            )
            results.append(
                EnterpriseActivityBrief(
                    id=activity.id,
                    title=activity.title,
                    performed_on=activity.performed_on,
                    status=activity.status.value if activity.status else "completed",
                    semantic_type=semantic,
                    activity_type_name=type_name,
                )
            )
        return results

    def _activity_counts(self, parcel_id: UUID) -> dict[str, int]:
        stmt = (
            select(Activity.semantic_type, func.count())
            .where(Activity.parcel_id == parcel_id)
            .group_by(Activity.semantic_type)
        )
        counts: dict[str, int] = {}
        for semantic, count in self.db.execute(stmt).all():
            key = semantic.value if semantic is not None else ActivitySemanticType.OTHER.value
            counts[key] = int(count or 0)
        return counts

    def _planting_year_distribution(self, parcel_id: UUID) -> dict[int, int]:
        parcel = self.repo.get_parcel(parcel_id)
        if parcel is None:
            return {}
        distribution, _unknown = self._tree_age_inputs(parcel)
        return distribution

    def _harvest_years(self, parcel_id: UUID) -> list[int]:
        stmt = (
            select(extract("year", HarvestEvent.harvested_on))
            .where(
                HarvestEvent.parcel_id == parcel_id,
                HarvestEvent.scope_type == ScopeType.PARCEL,
                HarvestEvent.gross_quantity.is_not(None),
            )
            .distinct()
            .order_by(extract("year", HarvestEvent.harvested_on).desc())
        )
        return [int(year) for year in self.db.scalars(stmt).all() if year is not None]

    def _latest_harvest_kg(self, parcel_id: UUID) -> Decimal | None:
        year_stmt = (
            select(extract("year", HarvestEvent.harvested_on))
            .where(
                HarvestEvent.parcel_id == parcel_id,
                HarvestEvent.scope_type == ScopeType.PARCEL,
                HarvestEvent.gross_quantity.is_not(None),
            )
            .order_by(HarvestEvent.harvested_on.desc())
            .limit(1)
        )
        year = self.db.scalar(year_stmt)
        if year is None:
            return None
        total, _count, _parcels = self._parcel_harvest_net_kg([parcel_id], int(year))
        return total

    def _parcel_rows_trees(self, parcel: Parcel) -> tuple[list[Row], list[Tree]]:
        rows = list(self.db.scalars(select(Row).where(Row.parcel_id == parcel.id)).all())
        trees = list(
            self.db.scalars(
                select(Tree).where(Tree.parcel_id == parcel.id, Tree.status == TreeStatus.ACTIVE)
            ).all()
        )
        return rows, trees

    def _tree_variety_label(
        self, tree: Tree, parcel: Parcel, rows_by_id: dict[UUID, Row] | None = None
    ) -> str:
        names = self._variety_names(parcel)
        default_name = names[0] if names else "Nepoznata sorta"
        label = (tree.variety or "").strip()
        if not label and rows_by_id is not None:
            row = rows_by_id.get(tree.row_id)
            if row is not None:
                label = (row.variety or "").strip()
        return label or default_name

    def _parcel_harvest_net_kg(
        self, parcel_ids: list[UUID], year: int
    ) -> tuple[Decimal | None, int, set[UUID]]:
        """Parcel-scoped net harvest in kg — same base as client production totals."""
        if not parcel_ids:
            return None, 0, set()
        events = list(
            self.db.scalars(
                select(HarvestEvent).where(
                    HarvestEvent.parcel_id.in_(parcel_ids),
                    extract("year", HarvestEvent.harvested_on) == year,
                    HarvestEvent.scope_type == ScopeType.PARCEL,
                    HarvestEvent.gross_quantity.is_not(None),
                )
            ).all()
        )
        if not events:
            return None, 0, set()
        total = Decimal("0")
        parcels: set[UUID] = set()
        found = False
        for event in events:
            kg = mass_to_kg(event.net_quantity, event.unit)
            if kg is None:
                continue
            total += kg
            found = True
            if event.parcel_id is not None:
                parcels.add(event.parcel_id)
        return (total if found else Decimal("0")), len(events), parcels

    def _tree_age_inputs(self, parcel: Parcel) -> tuple[dict[int, int], int]:
        rows, trees = self._parcel_rows_trees(parcel)
        return planting_year_distribution(parcel=parcel, rows=rows, trees=trees)

    def _expected_for_parcel(self, parcel: Parcel, reference_year: int) -> Decimal | None:
        distribution, unknown = self._tree_age_inputs(parcel)
        if not distribution and unknown == 0:
            return None
        totals = compute_expected_yield(
            distribution=distribution,
            unknown_tree_count=unknown,
            reference_year=reference_year,
            area_hectares=parcel.area_hectares,
        )
        if not totals.available:
            return None
        return totals.realistic_kg

    def _build_plan_item(
        self,
        plan: EnterpriseYieldPlan,
        parcel: Parcel,
        reference_year: int,
        scenario: ExpectedYieldScenario,
        assumptions: dict | None,
    ) -> EnterpriseYieldPlanItem:
        distribution, unknown = self._tree_age_inputs(parcel)
        tree_count = sum(distribution.values()) + unknown
        missing = self._missing_fields(parcel)
        totals = compute_expected_yield(
            distribution=distribution,
            unknown_tree_count=unknown,
            reference_year=reference_year,
            area_hectares=parcel.area_hectares,
        )
        if not totals.available:
            forecast = Decimal("0")
        else:
            kg_map = {
                ExpectedYieldScenario.PESSIMISTIC: totals.pessimistic_kg or Decimal("0"),
                ExpectedYieldScenario.REALISTIC: totals.realistic_kg or Decimal("0"),
                ExpectedYieldScenario.OPTIMISTIC: totals.optimistic_kg or Decimal("0"),
            }
            forecast = kg_map.get(scenario, totals.realistic_kg or Decimal("0"))

        area = parcel.area_hectares
        per_ha = None
        if area and area > 0 and forecast is not None:
            per_ha = (forecast / area).quantize(Decimal("0.01"))
        tonnes = (forecast / Decimal("1000")).quantize(Decimal("0.0001")) if forecast else None

        return EnterpriseYieldPlanItem(
            yield_plan_id=plan.id,
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            crop=parcel.default_variety or "lesnik",
            forecast_area_ha=area,
            forecast_tree_count=tree_count,
            forecast_yield_kg=forecast or Decimal("0"),
            forecast_yield_tonnes=tonnes,
            forecast_yield_kg_per_ha=per_ha,
            scenario_assumptions=assumptions or {},
            source_snapshot={
                "reference_year": reference_year,
                "planting_year_counts": {str(k): v for k, v in distribution.items()},
                "unknown_tree_count": unknown,
                "tree_count": tree_count,
                "area_hectares": str(area) if area is not None else None,
                "scenario": scenario.value,
                "profile_version": totals.profile_version,
            },
            calculation_version=CALCULATION_VERSION,
            data_quality={
                "missing_fields": missing,
                "included": totals.available,
                "warning": totals.message if not totals.available else totals.precision_note,
            },
        )

    def _plan_read(self, plan: EnterpriseYieldPlan) -> EnterpriseYieldPlanRead:
        items: list[EnterpriseYieldPlanItemRead] = []
        total = Decimal("0")
        for item in plan.items:
            parcel = self.repo.get_parcel(item.parcel_id)
            farm = self.repo.get_farm(item.farm_id)
            total += item.forecast_yield_kg or Decimal("0")
            items.append(
                EnterpriseYieldPlanItemRead(
                    id=item.id,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    yield_plan_id=item.yield_plan_id,
                    farm_id=item.farm_id,
                    parcel_id=item.parcel_id,
                    crop=item.crop,
                    forecast_area_ha=item.forecast_area_ha,
                    forecast_tree_count=item.forecast_tree_count,
                    forecast_yield_kg=item.forecast_yield_kg,
                    forecast_yield_tonnes=item.forecast_yield_tonnes,
                    forecast_yield_kg_per_ha=item.forecast_yield_kg_per_ha,
                    scenario_assumptions=item.scenario_assumptions or {},
                    source_snapshot=item.source_snapshot or {},
                    calculation_version=item.calculation_version,
                    data_quality=item.data_quality or {},
                    parcel_name=parcel.name if parcel else None,
                    farm_name=farm.name if farm else None,
                )
            )
        return EnterpriseYieldPlanRead(
            id=plan.id,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            organization_id=plan.organization_id,
            planning_season_id=plan.planning_season_id,
            name=plan.name,
            description=plan.description,
            scenario_type=plan.scenario_type,
            status=plan.status,
            assumptions=plan.assumptions or {},
            calculation_version=plan.calculation_version,
            created_by_id=plan.created_by_id,
            items=items,
            total_forecast_kg=total,
        )

    def compare_yield_plan(
        self, user: User, organization_id: UUID, plan_id: UUID
    ) -> EnterpriseYieldComparison:
        self.access.require_reader(user, organization_id)
        plan = self.repo.get_yield_plan(organization_id, plan_id)
        if plan is None:
            raise NotFoundError("Plan prinosa nije pronađen")
        season = self.repo.get_season(organization_id, plan.planning_season_id)
        if season is None:
            raise NotFoundError("Sezona nije pronađena")

        rows: list[EnterpriseYieldComparisonRow] = []
        total_forecast = Decimal("0")
        actual_sum = Decimal("0")
        has_any_actual = False
        with_harvest = 0
        missing = 0
        notes: list[str] = []

        for item in plan.items:
            parcel = self.repo.get_parcel(item.parcel_id)
            farm = self.repo.get_farm(item.farm_id)
            forecast = item.forecast_yield_kg or Decimal("0")
            total_forecast += forecast

            actual, event_count, _parcels = self._parcel_harvest_net_kg(
                [item.parcel_id], season.year
            )
            if actual is not None:
                has_any_actual = True
                actual_sum += actual
                with_harvest += 1
            else:
                missing += 1
                event_count = 0

            difference: Decimal | None = None
            difference_percent: float | None = None
            status = "missing_harvest"
            if actual is None:
                status = "missing_harvest"
            elif forecast <= 0:
                status = "forecast_zero"
                difference = actual - forecast
            else:
                difference = actual - forecast
                difference_percent = float((difference / forecast) * Decimal("100"))
                status = "compared"

            rows.append(
                EnterpriseYieldComparisonRow(
                    parcel_id=item.parcel_id,
                    farm_id=item.farm_id,
                    parcel_name=parcel.name if parcel else None,
                    farm_name=farm.name if farm else None,
                    forecast_yield_kg=forecast,
                    actual_net_yield_kg=actual,
                    difference_kg=difference,
                    difference_percent=difference_percent,
                    status=status,
                    harvest_events=event_count,
                )
            )

        if missing:
            notes.append(
                f"{missing} parcela nema evidentiranu berbu za {season.year}. — to nije nula prinosa."
            )

        return EnterpriseYieldComparison(
            plan_id=plan.id,
            plan_name=plan.name,
            scenario_type=plan.scenario_type,
            season_year=season.year,
            total_forecast_kg=total_forecast,
            total_actual_kg=actual_sum if has_any_actual else None,
            parcels_with_harvest=with_harvest,
            parcels_missing_harvest=missing,
            rows=rows,
            notes=notes,
        )

    def list_linkable_farms(
        self, user: User, organization_id: UUID, *, q: str | None = None
    ) -> list[EnterpriseFarmCandidate]:
        """Minimal farm directory for linking suppliers (id/name/location only)."""
        self.access.require_admin(user, organization_id)
        linked = {link.farm_id for link in self.repo.list_supplier_links(organization_id)}
        stmt = select(Farm).order_by(Farm.name.asc())
        farms = list(self.db.scalars(stmt).all())
        results: list[EnterpriseFarmCandidate] = []
        for farm in farms:
            if q:
                needle = q.lower()
                hay = f"{farm.name} {farm.location_name or ''}".lower()
                if needle not in hay:
                    continue
            results.append(
                EnterpriseFarmCandidate(
                    farm_id=farm.id,
                    name=farm.name,
                    location_name=farm.location_name,
                    already_linked=farm.id in linked,
                )
            )
        return results

    def list_assignable_parcels(
        self, user: User, organization_id: UUID, farm_id: UUID
    ) -> list[EnterpriseAssignableParcel]:
        self.access.require_admin(user, organization_id)
        self.access.require_supplier_link(organization_id, farm_id)
        assigned = {
            a.parcel_id
            for a in self.repo.list_parcel_assignments(organization_id)
            if a.farm_id == farm_id
        }
        parcels = list(
            self.db.scalars(select(Parcel).where(Parcel.farm_id == farm_id).order_by(Parcel.name)).all()
        )
        return [
            EnterpriseAssignableParcel(
                parcel_id=parcel.id,
                farm_id=parcel.farm_id,
                name=parcel.name,
                area_hectares=parcel.area_hectares,
                already_assigned=parcel.id in assigned,
            )
            for parcel in parcels
        ]

    def get_parcel_twin(
        self, user: User, organization_id: UUID, parcel_id: UUID
    ) -> OrchardTwinRead:
        """Read-only digital twin for an assigned parcel (via producer owner scope)."""
        self.access.require_reader(user, organization_id)
        self.access.require_parcel_read(organization_id, parcel_id)
        parcel = self.repo.get_parcel(parcel_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        farm = self.repo.get_farm(parcel.farm_id)
        if farm is None:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return OrchardService(self.db).get_twin(parcel_id, farm.owner_id)

    def satellite_history(
        self,
        user: User,
        organization_id: UUID,
        parcel_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        from app.services.satellite import SatelliteService

        self.access.require_reader(user, organization_id)
        self.access.require_parcel_read(organization_id, parcel_id)
        return SatelliteService(self.db).history_for_parcel(
            parcel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def export_parcels_csv(self, user: User, organization_id: UUID) -> str:
        self.access.require_reader(user, organization_id)
        parcels = self.list_parcels(user, organization_id)
        lines = [
            "parcel_id,parcel_name,farm_name,area_ha,tree_count,variety,planting_year,completeness_pct,missing_fields"
        ]
        for parcel in parcels:
            lines.append(
                ",".join(
                    [
                        str(parcel.parcel_id),
                        _csv(parcel.parcel_name),
                        _csv(parcel.farm_name),
                        str(parcel.area_hectares) if parcel.area_hectares is not None else "",
                        str(parcel.tree_count),
                        _csv(parcel.default_variety or ""),
                        str(parcel.default_planting_year or ""),
                        str(parcel.completeness_score or ""),
                        _csv(";".join(parcel.missing_fields)),
                    ]
                )
            )
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.EXPORT_GENERATED.value,
            entity_type="parcels_csv",
            details={"row_count": len(parcels)},
        )
        self.db.flush()
        return "\n".join(lines) + "\n"

    def export_yield_plan_csv(
        self, user: User, organization_id: UUID, plan_id: UUID
    ) -> str:
        self.access.require_reader(user, organization_id)
        plan = self.get_yield_plan(user, organization_id, plan_id)
        comparison = self.compare_yield_plan(user, organization_id, plan_id)
        by_parcel = {row.parcel_id: row for row in comparison.rows}
        lines = [
            "plan_name,scenario,season_year,parcel_name,farm_name,forecast_kg,actual_kg,difference_kg,difference_pct,status,note"
        ]
        for item in plan.items:
            row = by_parcel.get(item.parcel_id)
            lines.append(
                ",".join(
                    [
                        _csv(plan.name),
                        plan.scenario_type.value,
                        str(comparison.season_year),
                        _csv(item.parcel_name or ""),
                        _csv(item.farm_name or ""),
                        str(item.forecast_yield_kg),
                        str(row.actual_net_yield_kg) if row and row.actual_net_yield_kg is not None else "",
                        str(row.difference_kg) if row and row.difference_kg is not None else "",
                        str(row.difference_percent) if row and row.difference_percent is not None else "",
                        row.status if row else "",
                        "forecast_not_actual",
                    ]
                )
            )
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.EXPORT_GENERATED.value,
            entity_type="yield_plan_csv",
            entity_id=plan_id,
            details={"row_count": len(plan.items)},
        )
        self.db.flush()
        return "\n".join(lines) + "\n"


def _csv(value: str) -> str:
    escaped = value.replace('"', '""')
    if any(ch in escaped for ch in [",", '"', "\n"]):
        return f'"{escaped}"'
    return escaped


def ensure_organization(
    db: Session,
    *,
    name: str,
    slug: str | None = None,
) -> EnterpriseOrganization:
    repo = EnterpriseRepository(db)
    resolved_slug = slug or _slugify(name)
    existing = repo.get_org_by_slug(resolved_slug)
    if existing is not None:
        return existing
    org = EnterpriseOrganization(
        name=name,
        slug=resolved_slug,
        status=EnterpriseOrgStatus.ACTIVE,
        default_currency="RSD",
        timezone="Europe/Belgrade",
        default_crop="lesnik",
        completeness_requirements={
            "required_fields": [
                "area_hectares",
                "variety",
                "planting_year",
                "trees",
            ]
        },
        default_scenario=EnterpriseScenarioType.REALISTIC,
    )
    db.add(org)
    db.flush()
    return org
