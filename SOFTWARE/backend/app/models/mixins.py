from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ScopeType, pg_enum


class ScopedEntityMixin:
    """Activities and costs can belong to a farm, parcel, row, or tree.

    Parent identifiers are denormalized so later cost and activity
    aggregations can filter by orchard, parcel, row, or tree without
    walking the hierarchy.
    """

    scope_type: Mapped[ScopeType] = mapped_column(
        pg_enum(ScopeType, "scope_type"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    row_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orchard_rows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tree_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("trees.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    @classmethod
    def scope_check_constraint(cls, table_name: str) -> CheckConstraint:
        return CheckConstraint(
            """
            (scope_type = 'farm' AND parcel_id IS NULL AND row_id IS NULL AND tree_id IS NULL)
            OR (scope_type = 'parcel' AND parcel_id IS NOT NULL AND row_id IS NULL AND tree_id IS NULL)
            OR (scope_type = 'row' AND parcel_id IS NOT NULL AND row_id IS NOT NULL AND tree_id IS NULL)
            OR (scope_type = 'tree' AND parcel_id IS NOT NULL AND row_id IS NOT NULL AND tree_id IS NOT NULL)
            """,
            name=f"ck_{table_name}_scope_matches_ids",
        )
