"""Enterprise organization, membership, supplier/parcel assignments, planning.

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-10-16 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "y4z5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

enterprise_org_status = postgresql.ENUM("active", "inactive", name="enterprise_org_status", create_type=False)
enterprise_membership_role = postgresql.ENUM(
    "enterprise_admin",
    "enterprise_analyst",
    "enterprise_viewer",
    name="enterprise_membership_role",
    create_type=False,
)
enterprise_membership_status = postgresql.ENUM(
    "active", "inactive", "invited", name="enterprise_membership_status", create_type=False
)
enterprise_relationship_status = postgresql.ENUM(
    "active", "inactive", "pending", name="enterprise_relationship_status", create_type=False
)
enterprise_assignment_status = postgresql.ENUM(
    "active", "inactive", "pending", name="enterprise_assignment_status", create_type=False
)
enterprise_season_status = postgresql.ENUM(
    "draft", "active", "closed", name="enterprise_season_status", create_type=False
)
enterprise_scenario_type = postgresql.ENUM(
    "conservative",
    "realistic",
    "optimistic",
    "custom",
    name="enterprise_scenario_type",
    create_type=False,
)
enterprise_yield_plan_status = postgresql.ENUM(
    "draft", "published", "archived", name="enterprise_yield_plan_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        postgresql.ENUM("active", "inactive", name="enterprise_org_status"),
        postgresql.ENUM(
            "enterprise_admin",
            "enterprise_analyst",
            "enterprise_viewer",
            name="enterprise_membership_role",
        ),
        postgresql.ENUM("active", "inactive", "invited", name="enterprise_membership_status"),
        postgresql.ENUM("active", "inactive", "pending", name="enterprise_relationship_status"),
        postgresql.ENUM("active", "inactive", "pending", name="enterprise_assignment_status"),
        postgresql.ENUM("draft", "active", "closed", name="enterprise_season_status"),
        postgresql.ENUM(
            "conservative",
            "realistic",
            "optimistic",
            "custom",
            name="enterprise_scenario_type",
        ),
        postgresql.ENUM("draft", "published", "archived", name="enterprise_yield_plan_status"),
    ):
        enum_type.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "enterprise_organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
        sa.Column("default_currency", sa.String(8), nullable=False, server_default="RSD"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Belgrade"),
        sa.Column("default_crop", sa.String(128), nullable=True),
        sa.Column("status", enterprise_org_status, nullable=False, server_default="active"),
        sa.Column("completeness_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("default_scenario", enterprise_scenario_type, nullable=False, server_default="realistic"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_enterprise_organizations_slug", "enterprise_organizations", ["slug"], unique=True)

    op.create_table(
        "enterprise_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", enterprise_membership_role, nullable=False, server_default="enterprise_viewer"),
        sa.Column("status", enterprise_membership_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_enterprise_membership_org_user"),
    )
    op.create_index("ix_enterprise_memberships_organization_id", "enterprise_memberships", ["organization_id"])
    op.create_index("ix_enterprise_memberships_user_id", "enterprise_memberships", ["user_id"])

    op.create_table(
        "enterprise_supplier_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", enterprise_relationship_status, nullable=False, server_default="active"),
        sa.Column("relationship_start", sa.Date(), nullable=True),
        sa.Column("relationship_end", sa.Date(), nullable=True),
        sa.Column("internal_code", sa.String(64), nullable=True),
        sa.Column("internal_group", sa.String(128), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("assigned_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "farm_id", name="uq_enterprise_supplier_org_farm"),
    )
    op.create_index("ix_enterprise_supplier_links_organization_id", "enterprise_supplier_links", ["organization_id"])
    op.create_index("ix_enterprise_supplier_links_farm_id", "enterprise_supplier_links", ["farm_id"])
    op.create_index("ix_enterprise_supplier_links_status", "enterprise_supplier_links", ["status"])
    op.create_index("ix_enterprise_supplier_links_internal_code", "enterprise_supplier_links", ["internal_code"])
    op.create_index("ix_enterprise_supplier_links_internal_group", "enterprise_supplier_links", ["internal_group"])

    op.create_table(
        "enterprise_parcel_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parcels.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", enterprise_assignment_status, nullable=False, server_default="active"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("assigned_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "parcel_id", name="uq_enterprise_parcel_assignment_org_parcel"),
    )
    op.create_index("ix_enterprise_parcel_assignments_organization_id", "enterprise_parcel_assignments", ["organization_id"])
    op.create_index("ix_enterprise_parcel_assignments_farm_id", "enterprise_parcel_assignments", ["farm_id"])
    op.create_index("ix_enterprise_parcel_assignments_parcel_id", "enterprise_parcel_assignments", ["parcel_id"])
    op.create_index("ix_enterprise_parcel_assignments_status", "enterprise_parcel_assignments", ["status"])

    op.create_table(
        "enterprise_planning_seasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", enterprise_season_status, nullable=False, server_default="draft"),
        sa.Column("supply_target_kg", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "year", name="uq_enterprise_planning_season_org_year"),
    )
    op.create_index("ix_enterprise_planning_seasons_organization_id", "enterprise_planning_seasons", ["organization_id"])
    op.create_index("ix_enterprise_planning_seasons_year", "enterprise_planning_seasons", ["year"])

    op.create_table(
        "enterprise_yield_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planning_season_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_planning_seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scenario_type", enterprise_scenario_type, nullable=False, server_default="realistic"),
        sa.Column("status", enterprise_yield_plan_status, nullable=False, server_default="draft"),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("calculation_version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_enterprise_yield_plans_organization_id", "enterprise_yield_plans", ["organization_id"])
    op.create_index("ix_enterprise_yield_plans_planning_season_id", "enterprise_yield_plans", ["planning_season_id"])

    op.create_table(
        "enterprise_yield_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("yield_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_yield_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parcels.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("crop", sa.String(128), nullable=False, server_default="lesnik"),
        sa.Column("forecast_area_ha", sa.Numeric(10, 4), nullable=True),
        sa.Column("forecast_tree_count", sa.Integer(), nullable=True),
        sa.Column("forecast_yield_kg", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("forecast_yield_tonnes", sa.Numeric(14, 4), nullable=True),
        sa.Column("forecast_yield_kg_per_ha", sa.Numeric(14, 2), nullable=True),
        sa.Column("scenario_assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("calculation_version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("data_quality", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("yield_plan_id", "parcel_id", name="uq_enterprise_yield_plan_item_plan_parcel"),
    )
    op.create_index("ix_enterprise_yield_plan_items_yield_plan_id", "enterprise_yield_plan_items", ["yield_plan_id"])
    op.create_index("ix_enterprise_yield_plan_items_farm_id", "enterprise_yield_plan_items", ["farm_id"])
    op.create_index("ix_enterprise_yield_plan_items_parcel_id", "enterprise_yield_plan_items", ["parcel_id"])

    op.create_table(
        "enterprise_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_enterprise_audit_events_organization_id", "enterprise_audit_events", ["organization_id"])
    op.create_index("ix_enterprise_audit_events_action", "enterprise_audit_events", ["action"])
    op.create_index("ix_enterprise_audit_events_created_at", "enterprise_audit_events", ["created_at"])

    op.create_table(
        "enterprise_follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_enterprise_follow_ups_organization_id", "enterprise_follow_ups", ["organization_id"])
    op.create_index("ix_enterprise_follow_ups_farm_id", "enterprise_follow_ups", ["farm_id"])
    op.create_index("ix_enterprise_follow_ups_parcel_id", "enterprise_follow_ups", ["parcel_id"])


def downgrade() -> None:
    op.drop_table("enterprise_follow_ups")
    op.drop_table("enterprise_audit_events")
    op.drop_table("enterprise_yield_plan_items")
    op.drop_table("enterprise_yield_plans")
    op.drop_table("enterprise_planning_seasons")
    op.drop_table("enterprise_parcel_assignments")
    op.drop_table("enterprise_supplier_links")
    op.drop_table("enterprise_memberships")
    op.drop_table("enterprise_organizations")
    op.drop_column("users", "must_change_password")

    bind = op.get_bind()
    for name in (
        "enterprise_yield_plan_status",
        "enterprise_scenario_type",
        "enterprise_season_status",
        "enterprise_assignment_status",
        "enterprise_relationship_status",
        "enterprise_membership_status",
        "enterprise_membership_role",
        "enterprise_org_status",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
