"""Read existing parcel alerts for an Enterprise organization.

Does not run satellite sync or AI, and does not change producer alert status.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.enterprise.access import EnterpriseAccess
from app.enterprise.csv_safe import csv_cell
from app.enterprise.alert_watch import (
    affected_indices,
    alert_kpis,
    alert_scene_date,
    filter_alert_rows,
    intelligence_href,
)
from app.models.enterprise import EnterpriseAlertReview
from app.models.enums import EnterpriseAuditAction, SatelliteProcessingStatus
from app.models.farm import Farm
from app.models.intelligence import ParcelAlert, ParcelAnalysisRun
from app.models.parcel import Parcel
from app.models.satellite import SatelliteAnomaly, SatelliteObservation
from app.models.user import User
from app.repositories.enterprise import EnterpriseRepository
from app.schemas.enterprise import (
    EnterpriseAlertReviewRead,
    EnterpriseAlertWatchItem,
    EnterpriseAlertWatchPage,
    EnterpriseAlertWatchReview,
)


class EnterpriseAlertWatchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.access = EnterpriseAccess(db)
        self.repo = EnterpriseRepository(db)

    def list_alerts(
        self,
        user: User,
        organization_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        farm_id: UUID | None = None,
        parcel_id: UUID | None = None,
        index: str | None = None,
        severity: str | None = None,
        alert_status: str | None = None,
        review_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> EnterpriseAlertWatchPage:
        self.access.require_reader(user, organization_id)
        if date_from and date_to and date_from > date_to:
            date_from, date_to = date_to, date_from
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        parcel_ids = self.access.readable_parcel_ids(organization_id)
        if parcel_id is not None and parcel_id not in parcel_ids:
            return _empty_page(organization_id, limit, offset)
        scope = {parcel_id} if parcel_id is not None else set(parcel_ids)
        if farm_id is not None and scope:
            farm_parcels = set(
                self.db.scalars(
                    select(Parcel.id).where(
                        Parcel.id.in_(scope),
                        Parcel.farm_id == farm_id,
                    )
                ).all()
            )
            scope &= farm_parcels
        if not scope:
            return _empty_page(organization_id, limit, offset)

        alerts = list(
            self.db.scalars(
                select(ParcelAlert)
                .where(ParcelAlert.parcel_id.in_(scope))
                .order_by(ParcelAlert.created_at.desc())
            ).all()
        )
        if not alerts:
            anomaly_count = self._anomaly_count(scope, date_from, date_to)
            kpis = alert_kpis([], satellite_anomaly_count=anomaly_count)
            return EnterpriseAlertWatchPage(
                organization_id=organization_id,
                **kpis,
                limit=limit,
                offset=offset,
            )

        parcels = {
            item.id: item
            for item in self.db.scalars(select(Parcel).where(Parcel.id.in_(scope))).all()
        }
        farm_ids = {parcel.farm_id for parcel in parcels.values()}
        farms = {
            item.id: item
            for item in self.db.scalars(select(Farm).where(Farm.id.in_(farm_ids))).all()
        } if farm_ids else {}
        owner_ids = {farm.owner_id for farm in farms.values() if farm.owner_id}
        owners = {
            item.id: item
            for item in self.db.scalars(select(User).where(User.id.in_(owner_ids))).all()
        } if owner_ids else {}

        alert_ids = [item.id for item in alerts]
        review_rows = list(
            self.db.scalars(
                select(EnterpriseAlertReview).where(
                    EnterpriseAlertReview.organization_id == organization_id,
                    EnterpriseAlertReview.alert_id.in_(alert_ids),
                )
            ).all()
        )
        reviews = {item.alert_id: item for item in review_rows}
        reviewer_ids = {item.reviewed_by_id for item in review_rows if item.reviewed_by_id}
        reviewers = {
            item.id: item
            for item in self.db.scalars(select(User).where(User.id.in_(reviewer_ids))).all()
        } if reviewer_ids else {}
        run_ids = {item.analysis_run_id for item in alerts if item.analysis_run_id}
        runs = {
            item.id: item
            for item in self.db.scalars(
                select(ParcelAnalysisRun).where(ParcelAnalysisRun.id.in_(run_ids))
            ).all()
        } if run_ids else {}
        latest_obs = self._latest_observations(scope)
        obs_ids = [item.id for item in latest_obs.values()]
        anomalies = self._anomalies_for(obs_ids)

        rows: list[dict] = []
        for alert in alerts:
            parcel = parcels.get(alert.parcel_id)
            if parcel is None:
                continue
            farm = farms.get(parcel.farm_id)
            evidence = alert.evidence if isinstance(alert.evidence, dict) else {}
            scene = alert_scene_date(evidence, None)
            review = reviews.get(alert.id)
            reviewer = reviewers.get(review.reviewed_by_id) if review and review.reviewed_by_id else None
            observation = latest_obs.get(alert.parcel_id)
            indices = affected_indices(evidence)
            zone_keys = [
                str(key)
                for key in (evidence.get("zone_keys") or [])
                if isinstance(key, str) and key.strip()
            ]
            tree_public_ids = [
                str(key).strip().upper()
                for key in (evidence.get("tree_public_ids") or [])
                if isinstance(key, str) and key.strip()
            ]
            kinds = _kinds_for_alert(anomalies.get(observation.id, []) if observation else [], zone_keys)
            rows.append(
                {
                    "alert": alert,
                    "alert_id": str(alert.id),
                    "parcel": parcel,
                    "farm": farm,
                    "owner": owners.get(farm.owner_id) if farm and farm.owner_id else None,
                    "farm_id": str(parcel.farm_id),
                    "parcel_id": str(parcel.id),
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "scene_date": scene,
                    "reviewed": review is not None,
                    "review": review,
                    "reviewer_name": reviewer.full_name if reviewer else None,
                    "affected_indices": indices,
                    "zone_keys": zone_keys,
                    "tree_public_ids": tree_public_ids,
                    "kinds": kinds,
                    "observation": observation,
                    "run": runs.get(alert.analysis_run_id) if alert.analysis_run_id else None,
                }
            )

        filtered = filter_alert_rows(
            rows,
            date_from=date_from,
            date_to=date_to,
            farm_id=str(farm_id) if farm_id else None,
            parcel_id=str(parcel_id) if parcel_id else None,
            index=index,
            severity=severity,
            alert_status=alert_status,
            review_status=review_status,
        )
        anomaly_count = self._anomaly_count(scope, date_from, date_to)
        kpis = alert_kpis(filtered, satellite_anomaly_count=anomaly_count)
        page = filtered[offset : offset + limit]
        return EnterpriseAlertWatchPage(
            organization_id=organization_id,
            **kpis,
            limit=limit,
            offset=offset,
            items=[self._item(row) for row in page],
        )

    def export_csv(
        self,
        user: User,
        organization_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        farm_id: UUID | None = None,
        parcel_id: UUID | None = None,
        index: str | None = None,
        severity: str | None = None,
        alert_status: str | None = None,
        review_status: str | None = None,
    ) -> str:
        """Same filters as the alert list. Empty cells stay empty."""
        header = [
            "alert_id",
            "supplier",
            "parcel",
            "observation_date",
            "index",
            "anomaly_kind",
            "severity",
            "alert_status",
            "company_review_status",
            "last_analysis_at",
            "ai_summary",
        ]
        lines = [",".join(header)]
        offset = 0
        exported = 0
        while offset < 5000:
            page = self.list_alerts(
                user,
                organization_id,
                date_from=date_from,
                date_to=date_to,
                farm_id=farm_id,
                parcel_id=parcel_id,
                index=index,
                severity=severity,
                alert_status=alert_status,
                review_status=review_status,
                limit=100,
                offset=offset,
            )
            for item in page.items:
                review = "reviewed" if item.company_review is not None else ""
                lines.append(
                    ",".join(
                        [
                            csv_cell(item.alert_id),
                            csv_cell(item.producer_name),
                            csv_cell(item.parcel_name),
                            csv_cell(item.observation_date),
                            csv_cell(";".join(item.affected_indices)),
                            csv_cell(";".join(item.anomaly_kinds)),
                            csv_cell(item.severity),
                            csv_cell(item.status),
                            csv_cell(review),
                            csv_cell(item.last_analysis_at.isoformat() if item.last_analysis_at else None),
                            csv_cell(item.summary),
                        ]
                    )
                )
            exported += len(page.items)
            offset += len(page.items)
            if offset >= page.alert_count or not page.items:
                break
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.EXPORT_GENERATED.value,
            entity_type="intelligence_alert_csv",
            entity_id=None,
            details={"row_count": exported},
        )
        self.db.flush()
        return "\n".join(lines) + "\n"

    def mark_reviewed(
        self,
        user: User,
        organization_id: UUID,
        alert_id: UUID,
        *,
        note: str | None = None,
    ) -> EnterpriseAlertReviewRead:
        self.access.require_plan_writer(user, organization_id)
        alert = self.db.get(ParcelAlert, alert_id)
        if alert is None or alert.parcel_id not in self.access.readable_parcel_ids(organization_id):
            raise NotFoundError("Alert nije pronađen")
        producer_status = alert.status
        review = self.db.scalars(
            select(EnterpriseAlertReview).where(
                EnterpriseAlertReview.organization_id == organization_id,
                EnterpriseAlertReview.alert_id == alert_id,
            )
        ).first()
        now = datetime.now(timezone.utc)
        cleaned = note.strip() if isinstance(note, str) and note.strip() else None
        if review is None:
            review = EnterpriseAlertReview(
                organization_id=organization_id,
                alert_id=alert_id,
                reviewed_by_id=user.id,
                reviewed_at=now,
                note=cleaned,
            )
            self.db.add(review)
        else:
            review.reviewed_by_id = user.id
            review.reviewed_at = now
            review.note = cleaned
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.ALERT_REVIEWED.value,
            entity_type="parcel_alert",
            entity_id=alert.id,
            details={"review_only": True, "producer_status": producer_status.value},
        )
        self.db.flush()
        return EnterpriseAlertReviewRead(
            alert_id=alert.id,
            organization_id=organization_id,
            reviewed_at=review.reviewed_at,
            reviewed_by_name=user.full_name,
            note=review.note,
            producer_status=producer_status.value,
        )

    def _latest_observations(self, parcel_ids: set[UUID]) -> dict[UUID, SatelliteObservation]:
        if not parcel_ids:
            return {}
        rows = list(
            self.db.scalars(
                select(SatelliteObservation)
                .where(
                    SatelliteObservation.parcel_id.in_(parcel_ids),
                    SatelliteObservation.processing_status == SatelliteProcessingStatus.COMPLETED,
                )
                .distinct(SatelliteObservation.parcel_id)
                .order_by(
                    SatelliteObservation.parcel_id,
                    SatelliteObservation.acquisition_date.desc(),
                )
            ).all()
        )
        return {item.parcel_id: item for item in rows}

    def _anomalies_for(self, observation_ids: list[UUID]) -> dict[UUID, list[SatelliteAnomaly]]:
        if not observation_ids:
            return {}
        grouped: dict[UUID, list[SatelliteAnomaly]] = {}
        rows = self.db.scalars(
            select(SatelliteAnomaly).where(SatelliteAnomaly.observation_id.in_(observation_ids))
        ).all()
        for item in rows:
            grouped.setdefault(item.observation_id, []).append(item)
        return grouped

    def _anomaly_count(
        self,
        parcel_ids: set[UUID],
        date_from: date | None,
        date_to: date | None,
    ) -> int:
        if not parcel_ids:
            return 0
        stmt = (
            select(SatelliteAnomaly.id)
            .join(SatelliteObservation, SatelliteAnomaly.observation_id == SatelliteObservation.id)
            .where(SatelliteAnomaly.parcel_id.in_(parcel_ids))
        )
        if date_from is not None:
            stmt = stmt.where(SatelliteObservation.acquisition_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(SatelliteObservation.acquisition_date <= date_to)
        return len(list(self.db.scalars(stmt).all()))

    def _item(self, row: dict) -> EnterpriseAlertWatchItem:
        alert: ParcelAlert = row["alert"]
        parcel: Parcel = row["parcel"]
        farm: Farm | None = row["farm"]
        owner: User | None = row["owner"]
        observation: SatelliteObservation | None = row["observation"]
        run: ParcelAnalysisRun | None = row["run"]
        review: EnterpriseAlertReview | None = row["review"]
        public = (farm.public_producer_name or "").strip() if farm else ""
        producer = public or ((owner.full_name or "").strip() if owner else "") or (farm.name if farm else None)
        scene = row["scene_date"]
        processed = observation.processed_at if observation else None
        acquired = observation.acquisition_date if observation else None
        summary = (alert.summary or "").strip()
        actions = [item for item in (alert.recommended_actions or []) if isinstance(item, str) and item.strip()]
        return EnterpriseAlertWatchItem(
            alert_id=alert.id,
            parcel_id=parcel.id,
            farm_id=parcel.farm_id,
            producer_name=producer,
            parcel_name=parcel.name,
            observation_date=scene.isoformat() if isinstance(scene, date) and (alert.evidence or {}).get("observation_date") else None,
            latest_observation_date=acquired,
            processed_at=processed,
            affected_indices=list(row["affected_indices"]),
            anomaly_kinds=list(row["kinds"]),
            zone_keys=list(row["zone_keys"]),
            tree_public_ids=list(row.get("tree_public_ids") or []),
            severity=alert.severity.value,
            status=alert.status.value,
            title=alert.title,
            summary=summary or None,
            recommended_actions=actions,
            last_analysis_at=run.started_at if run else None,
            disclaimer=(
                "Sažetak je tumačenje zapisa, ne potvrđena agronomska dijagnoza."
                if summary
                else None
            ),
            company_review=_review_read(review, reviewer_name=row.get("reviewer_name")),
            intelligence_path=intelligence_href(str(parcel.id), str(alert.id)),
        )


def _review_read(
    review: EnterpriseAlertReview | None,
    *,
    reviewer_name: str | None,
) -> EnterpriseAlertWatchReview | None:
    if review is None:
        return None
    return EnterpriseAlertWatchReview(
        reviewed_at=review.reviewed_at,
        reviewed_by_name=reviewer_name,
        note=review.note,
    )


def _kinds_for_alert(anomalies: list[SatelliteAnomaly], zone_keys: list[str]) -> list[str]:
    if not zone_keys:
        return []
    kinds: list[str] = []
    for item in anomalies:
        if zone_keys and item.zone_key not in zone_keys:
            continue
        kind = item.kind.value if hasattr(item.kind, "value") else str(item.kind)
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def _empty_page(organization_id: UUID, limit: int, offset: int) -> EnterpriseAlertWatchPage:
    return EnterpriseAlertWatchPage(
        organization_id=organization_id,
        open_alerts=0,
        alert_count=0,
        satellite_anomaly_count=0,
        limit=limit,
        offset=offset,
    )
