"""Enterprise multi-tenant organization layer.

Producer-owned Farm / Parcel / Harvest / Activity records are never duplicated.
Enterprise stores only organization, membership, supplier/parcel assignments,
and Enterprise-owned planning/analytics artifacts.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseOrgStatus,
    EnterpriseRelationshipStatus,
    EnterpriseScenarioType,
    EnterpriseSeasonStatus,
    EnterpriseYieldPlanStatus,
    pg_enum,
)


class EnterpriseOrganization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RSD")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Belgrade")
    default_crop: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[EnterpriseOrgStatus] = mapped_column(
        pg_enum(EnterpriseOrgStatus, "enterprise_org_status"),
        nullable=False,
        default=EnterpriseOrgStatus.ACTIVE,
    )
    completeness_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    default_scenario: Mapped[EnterpriseScenarioType] = mapped_column(
        pg_enum(EnterpriseScenarioType, "enterprise_scenario_type"),
        nullable=False,
        default=EnterpriseScenarioType.REALISTIC,
    )

    memberships: Mapped[list[EnterpriseMembership]] = relationship(back_populates="organization")
    supplier_links: Mapped[list[EnterpriseSupplierLink]] = relationship(back_populates="organization")
    parcel_assignments: Mapped[list[EnterpriseParcelAssignment]] = relationship(
        back_populates="organization"
    )
    planning_seasons: Mapped[list[EnterprisePlanningSeason]] = relationship(
        back_populates="organization"
    )


class EnterpriseMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_enterprise_membership_org_user"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[EnterpriseMembershipRole] = mapped_column(
        pg_enum(EnterpriseMembershipRole, "enterprise_membership_role"),
        nullable=False,
        default=EnterpriseMembershipRole.ENTERPRISE_VIEWER,
    )
    status: Mapped[EnterpriseMembershipStatus] = mapped_column(
        pg_enum(EnterpriseMembershipStatus, "enterprise_membership_status"),
        nullable=False,
        default=EnterpriseMembershipStatus.ACTIVE,
    )

    organization: Mapped[EnterpriseOrganization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship("User")


class EnterpriseSupplierLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links an Enterprise org to an existing producer Farm (no Farm duplication)."""

    __tablename__ = "enterprise_supplier_links"
    __table_args__ = (
        UniqueConstraint("organization_id", "farm_id", name="uq_enterprise_supplier_org_farm"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[EnterpriseRelationshipStatus] = mapped_column(
        pg_enum(EnterpriseRelationshipStatus, "enterprise_relationship_status"),
        nullable=False,
        default=EnterpriseRelationshipStatus.ACTIVE,
        index=True,
    )
    relationship_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    relationship_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    internal_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    internal_group: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    assigned_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped[EnterpriseOrganization] = relationship(back_populates="supplier_links")
    farm: Mapped[Farm] = relationship("Farm")


class EnterpriseParcelAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit parcel-level read access. Assigning a supplier does not auto-grant parcels."""

    __tablename__ = "enterprise_parcel_assignments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "parcel_id",
            name="uq_enterprise_parcel_assignment_org_parcel",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[EnterpriseAssignmentStatus] = mapped_column(
        pg_enum(EnterpriseAssignmentStatus, "enterprise_assignment_status"),
        nullable=False,
        default=EnterpriseAssignmentStatus.ACTIVE,
        index=True,
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    assigned_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped[EnterpriseOrganization] = relationship(back_populates="parcel_assignments")
    farm: Mapped[Farm] = relationship("Farm")
    parcel: Mapped[Parcel] = relationship("Parcel")


class EnterprisePlanningSeason(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_planning_seasons"
    __table_args__ = (
        UniqueConstraint("organization_id", "year", name="uq_enterprise_planning_season_org_year"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[EnterpriseSeasonStatus] = mapped_column(
        pg_enum(EnterpriseSeasonStatus, "enterprise_season_status"),
        nullable=False,
        default=EnterpriseSeasonStatus.DRAFT,
    )
    supply_target_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    organization: Mapped[EnterpriseOrganization] = relationship(back_populates="planning_seasons")
    yield_plans: Mapped[list[EnterpriseYieldPlan]] = relationship(back_populates="planning_season")


class EnterpriseYieldPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_yield_plans"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planning_season_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_planning_seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[EnterpriseScenarioType] = mapped_column(
        pg_enum(EnterpriseScenarioType, "enterprise_scenario_type", create_type=False),
        nullable=False,
        default=EnterpriseScenarioType.REALISTIC,
    )
    status: Mapped[EnterpriseYieldPlanStatus] = mapped_column(
        pg_enum(EnterpriseYieldPlanStatus, "enterprise_yield_plan_status"),
        nullable=False,
        default=EnterpriseYieldPlanStatus.DRAFT,
    )
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    planning_season: Mapped[EnterprisePlanningSeason] = relationship(back_populates="yield_plans")
    items: Mapped[list[EnterpriseYieldPlanItem]] = relationship(
        back_populates="yield_plan",
        cascade="all, delete-orphan",
    )


class EnterpriseYieldPlanItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_yield_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "yield_plan_id",
            "parcel_id",
            name="uq_enterprise_yield_plan_item_plan_parcel",
        ),
    )

    yield_plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_yield_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    crop: Mapped[str] = mapped_column(String(128), nullable=False, default="lesnik")
    forecast_area_ha: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    forecast_tree_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forecast_yield_kg: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    forecast_yield_tonnes: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    forecast_yield_kg_per_ha: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    scenario_assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    data_quality: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    yield_plan: Mapped[EnterpriseYieldPlan] = relationship(back_populates="items")


class EnterpriseAuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "enterprise_audit_events"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class EnterpriseSupplierPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Enterprise purchase price card per linked supplier (bruto/neto € or RSD)."""

    __tablename__ = "enterprise_supplier_prices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "farm_id",
            "season_year",
            name="uq_enterprise_supplier_price_org_farm_year",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    season_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RSD")
    price_bruto_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    price_neto_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class EnterprisePurchase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Recorded purchase (otkup) from a linked supplier. Snapshot amounts for reporting."""

    __tablename__ = "enterprise_purchases"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchased_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_basis: Mapped[str] = mapped_column(String(16), nullable=False, default="bruto")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RSD")
    unit_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    # Price card snapshot at recording time (nullable if no card existed).
    price_bruto_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    price_neto_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class EnterpriseAlertReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Company review of an existing producer alert. Does not change producer status."""

    __tablename__ = "enterprise_alert_reviews"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "alert_id",
            name="uq_enterprise_alert_review_org_alert",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcel_alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class EnterpriseFollowUp(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Enterprise-owned follow-up / review note (not a producer activity)."""

    __tablename__ = "enterprise_follow_ups"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parcel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    alert_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcel_alerts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


# Late imports for relationship typing without circular import at module load.
from app.models.farm import Farm  # noqa: E402
from app.models.parcel import Parcel  # noqa: E402
from app.models.user import User  # noqa: E402
