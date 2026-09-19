from __future__ import annotations

import csv
import io
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import ScopeType
from app.services.activity import ActivityService


class ExportService:
    def __init__(self, db: Session) -> None:
        self.activities = ActivityService(db)

    def activities_csv(
        self,
        owner_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        parcel_id: UUID | None = None,
    ) -> str:
        records = self.activities.list_activities(
            owner_id, date_from=date_from, date_to=date_to, parcel_id=parcel_id
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "activity_id",
                "date",
                "activity_type",
                "title",
                "scope",
                "parcel",
                "row",
                "tree",
                "description",
                "quantity",
                "unit",
                "notes",
                "total_cost",
                "currency",
            ]
        )
        for item in records:
            writer.writerow(
                [
                    str(item.id),
                    item.performed_on.isoformat(),
                    item.activity_type.name,
                    item.title,
                    item.scope_type.value,
                    item.parcel_name or "",
                    ", ".join(str(number).zfill(2) for number in item.row_numbers)
                    if item.row_numbers
                    else (item.row_number if item.row_number is not None else ""),
                    item.tree_public_id or "",
                    item.description or "",
                    item.quantity if item.quantity is not None else "",
                    item.unit or "",
                    item.notes or "",
                    f"{item.total_cost:.2f}",
                    item.currency,
                ]
            )
        return output.getvalue()

    def costs_csv(
        self,
        owner_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        parcel_id: UUID | None = None,
    ) -> str:
        activities = self.activities.list_activities(
            owner_id, date_from=date_from, date_to=date_to, parcel_id=parcel_id
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "cost_id",
                "activity_id",
                "activity_type",
                "activity_title",
                "date",
                "category",
                "description",
                "amount",
                "currency",
                "scope",
                "parcel",
                "row",
                "tree",
                "notes",
                "receipt",
            ]
        )
        for activity in activities:
            for cost in activity.costs:
                if date_from is not None and cost.incurred_on < date_from:
                    continue
                if date_to is not None and cost.incurred_on > date_to:
                    continue
                writer.writerow(
                    [
                        str(cost.id),
                        str(cost.activity_id),
                        activity.activity_type.name,
                        activity.title,
                        cost.incurred_on.isoformat(),
                        cost.cost_category.name,
                        cost.description,
                        f"{cost.amount:.2f}",
                        cost.currency,
                        cost.scope_type.value if isinstance(cost.scope_type, ScopeType) else cost.scope_type,
                        cost.parcel_name or activity.parcel_name or "",
                        cost.row_number if cost.row_number is not None else (activity.row_number or ""),
                        cost.tree_public_id or activity.tree_public_id or "",
                        cost.notes or "",
                        cost.receipt_filename or "",
                    ]
                )
        return output.getvalue()
