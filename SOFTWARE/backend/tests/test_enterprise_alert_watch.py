"""Enterprise watch over existing parcel alerts. No database and no AI calls."""

from __future__ import annotations

import unittest
from datetime import date

from app.enterprise.access import WRITE_PLAN_ROLES
from app.enterprise.alert_watch import (
    alert_kpis,
    alert_scene_date,
    assignment_is_readable,
    filter_alert_rows,
    intelligence_href,
)
from app.models.enums import EnterpriseMembershipRole


TODAY = date(2026, 10, 20)


def _row(**overrides):
    base = {
        "alert_id": "a1",
        "farm_id": "farm-1",
        "parcel_id": "parcel-1",
        "severity": "WARNING",
        "status": "open",
        "reviewed": False,
        "affected_indices": ["ndvi", "ndre"],
        "scene_date": date(2026, 10, 1),
        "summary": None,
    }
    base.update(overrides)
    return base


class AssignmentScopeTests(unittest.TestCase):
    def test_multiple_suppliers_and_parcels_stay_separate(self) -> None:
        visible = []
        records = [
            ("org-a", "farm-1", "parcel-1", "active", "active", None, None),
            ("org-a", "farm-2", "parcel-2", "active", "active", None, None),
            ("org-a", "farm-2", "parcel-3", "inactive", "active", None, None),
        ]
        for org, _farm, parcel, assignment, supplier, start, end in records:
            if org == "org-a" and assignment_is_readable(
                assignment_status=assignment,
                supplier_status=supplier,
                valid_from=start,
                valid_until=end,
                on_date=TODAY,
            ):
                visible.append(parcel)
        self.assertEqual(visible, ["parcel-1", "parcel-2"])

    def test_inactive_assignment_is_hidden(self) -> None:
        self.assertFalse(
            assignment_is_readable(
                assignment_status="inactive",
                supplier_status="active",
                valid_from=None,
                valid_until=None,
                on_date=TODAY,
            )
        )

    def test_expired_valid_until_is_hidden(self) -> None:
        self.assertFalse(
            assignment_is_readable(
                assignment_status="active",
                supplier_status="active",
                valid_from=date(2026, 1, 1),
                valid_until=date(2026, 10, 19),
                on_date=TODAY,
            )
        )

    def test_other_organization_does_not_see_the_assignment(self) -> None:
        record = {"organization_id": "org-a", "parcel_id": "parcel-1"}
        readable = record["organization_id"] == "org-b" and assignment_is_readable(
            assignment_status="active",
            supplier_status="active",
            valid_from=None,
            valid_until=None,
            on_date=TODAY,
        )
        self.assertFalse(readable)

    def test_viewer_cannot_write_a_review(self) -> None:
        self.assertNotIn(EnterpriseMembershipRole.ENTERPRISE_VIEWER, WRITE_PLAN_ROLES)
        self.assertIn(EnterpriseMembershipRole.ENTERPRISE_ANALYST, WRITE_PLAN_ROLES)
        self.assertIn(EnterpriseMembershipRole.ENTERPRISE_ADMIN, WRITE_PLAN_ROLES)


class AlertRowTests(unittest.TestCase):
    def test_alert_without_summary_stays_in_the_list(self) -> None:
        rows = filter_alert_rows([_row(summary=None)])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["summary"])

    def test_multiple_indices_count_as_one_alert(self) -> None:
        rows = filter_alert_rows([_row(affected_indices=["ndvi", "ndre", "ndwi"])])
        self.assertEqual(len(rows), 1)
        self.assertEqual(alert_kpis(rows, satellite_anomaly_count=4)["alert_count"], 1)

    def test_duplicate_rows_collapse(self) -> None:
        rows = filter_alert_rows([_row(), _row(), _row(alert_id="a2", status="resolved")])
        self.assertEqual([row["alert_id"] for row in rows], ["a1", "a2"])

    def test_index_filter_does_not_split_the_alert(self) -> None:
        rows = filter_alert_rows([_row()], index="ndre")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["affected_indices"], ["ndvi", "ndre"])

    def test_navigation_uses_existing_intelligence_route(self) -> None:
        self.assertEqual(
            intelligence_href("parcel-9", "alert-3"),
            "/orchard/parcel-9/intelligence?alert=alert-3",
        )

    def test_company_review_filter_does_not_change_producer_status(self) -> None:
        source = _row(status="open", reviewed=True)
        rows = filter_alert_rows([source], review_status="reviewed")
        self.assertEqual(rows[0]["status"], "open")
        self.assertEqual(source["status"], "open")

    def test_kpis_separate_open_alerts_from_anomaly_rows(self) -> None:
        rows = filter_alert_rows(
            [
                _row(alert_id="open-1", status="open"),
                _row(alert_id="ack-1", status="acknowledged"),
                _row(alert_id="done-1", status="resolved"),
            ]
        )
        kpis = alert_kpis(rows, satellite_anomaly_count=7)
        self.assertEqual(kpis["open_alerts"], 2)
        self.assertEqual(kpis["alert_count"], 3)
        self.assertEqual(kpis["satellite_anomaly_count"], 7)

    def test_missing_scene_date_is_not_replaced_with_zero(self) -> None:
        self.assertIsNone(alert_scene_date({}, None))
        self.assertIsNone(alert_scene_date({"observation_date": ""}, None))
        kept = filter_alert_rows(
            [_row(scene_date=None)],
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 20),
        )
        self.assertEqual(kept, [])

    def test_date_and_severity_filters(self) -> None:
        rows = [
            _row(alert_id="in", scene_date=date(2026, 10, 2), severity="CRITICAL"),
            _row(alert_id="out", scene_date=date(2026, 9, 1), severity="INFO"),
        ]
        kept = filter_alert_rows(
            rows,
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 20),
            severity="CRITICAL",
        )
        self.assertEqual([row["alert_id"] for row in kept], ["in"])


if __name__ == "__main__":
    unittest.main()
