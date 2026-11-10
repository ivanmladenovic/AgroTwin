"""Continuous parcel intelligence — reuses get_ai_provider() only."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai import get_ai_provider
from app.ai.base import ChatMessage
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.intelligence.change_detection import detect_meaningful_changes
from app.intelligence.prompts import (
    PARCEL_INTELLIGENCE_DISCLAIMER,
    PARCEL_INTELLIGENCE_SYSTEM_PROMPT,
    PARCEL_INTELLIGENCE_USER_TEMPLATE,
)
from app.intelligence.satellite_context import sat_observation_summary, serialize_zone_anomalies
from app.intelligence.schema import ParcelIntelligenceAIResult
from app.models.activity import Activity
from app.models.disease import DiseaseCase
from app.models.enums import (
    ActivitySemanticType,
    DiseaseCaseStatus,
    ParcelAlertSeverity,
    ParcelAlertStatus,
    ParcelAnalysisEventKind,
    ParcelAnalysisRunStatus,
)
from app.models.farm import Farm
from app.models.intelligence import (
    ParcelAlert,
    ParcelAnalysisEvent,
    ParcelAnalysisRun,
    UserNotification,
)
from app.models.parcel import Parcel
from app.repositories.intelligence import IntelligenceRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.satellite import SatelliteRepository
from app.repositories.soil_lab import SoilLabAnalysisRepository
from app.repositories.tree import TreeRepository
from app.repositories.weather import WeatherCacheRepository
from app.satellite.zone_trees import (
    rewrite_zone_keys_in_strings,
    rewrite_zone_keys_in_text,
    trees_for_zone_keys,
    zone_tree_map,
)

_ZONE_KEY_RE = re.compile(r"\br(\d+)c(\d+)\b", re.IGNORECASE)
from app.schemas.intelligence import (
    IntelligenceDashboardRead,
    ParcelAlertRead,
    ParcelAnalysisRunRead,
    UserNotificationRead,
)

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {
    ParcelAlertSeverity.INFO: 1,
    ParcelAlertSeverity.WARNING: 2,
    ParcelAlertSeverity.CRITICAL: 3,
}

_ACTIVITY_KIND_MAP = {
    ActivitySemanticType.FERTILIZATION: ParcelAnalysisEventKind.ACTIVITY_FERTILIZATION,
    ActivitySemanticType.IRRIGATION: ParcelAnalysisEventKind.ACTIVITY_IRRIGATION,
    ActivitySemanticType.TREATMENT: ParcelAnalysisEventKind.ACTIVITY_PROTECTION,
}


class IntelligenceService:
    def __init__(self, db: Session, provider=None) -> None:
        self.db = db
        self.settings = get_settings()
        self.provider = provider or get_ai_provider()
        self.repo = IntelligenceRepository(db)
        self.parcels = ParcelRepository(db)
        self.satellites = SatelliteRepository(db)
        self.trees = TreeRepository(db)
        self.weather_cache = WeatherCacheRepository(db)
        self.soil_lab = SoilLabAnalysisRepository(db)

    # --- public API ---

    def enqueue_event(
        self,
        parcel_id: UUID,
        kind: ParcelAnalysisEventKind,
        payload: dict[str, Any] | None = None,
        *,
        process_inline: bool = False,
    ) -> ParcelAnalysisEvent:
        event = ParcelAnalysisEvent(
            parcel_id=parcel_id,
            kind=kind,
            payload=payload or {},
        )
        self.repo.add_event(event)
        self.db.commit()
        self.db.refresh(event)
        if process_inline and self.settings.ai_intelligence_enabled:
            try:
                self.process_parcel(parcel_id, force=kind == ParcelAnalysisEventKind.MANUAL_REQUEST)
            except Exception:  # noqa: BLE001
                logger.exception("Inline intelligence processing failed for %s", parcel_id)
        return event

    def enqueue_activity_event(self, parcel_id: UUID | None, semantic_type: ActivitySemanticType) -> None:
        if parcel_id is None:
            return
        kind = _ACTIVITY_KIND_MAP.get(semantic_type)
        if kind is None:
            return
        self.enqueue_event(parcel_id, kind, {"semantic_type": semantic_type.value})

    def get_dashboard(self, owner_id: UUID, parcel_id: UUID) -> IntelligenceDashboardRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return self._dashboard(parcel, read_only=False)

    def get_dashboard_readonly(self, parcel_id: UUID) -> IntelligenceDashboardRead:
        parcel = self.parcels.get_by_id(parcel_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return self._dashboard(parcel, read_only=True)

    def _dashboard(self, parcel, *, read_only: bool) -> IntelligenceDashboardRead:
        parcel_id = parcel.id
        open_alerts = self.repo.open_alerts(parcel_id)
        resolved = self.repo.resolved_alerts(parcel_id)
        last_run = self.repo.latest_run(parcel_id)
        last_ai = self.repo.latest_ai_run(parcel_id)
        next_at = None
        if last_run and last_run.started_at:
            next_at = last_run.started_at + timedelta(hours=self.settings.ai_analysis_min_interval_hours)
        return IntelligenceDashboardRead(
            parcel_id=parcel_id,
            parcel_name=parcel.name,
            available=True,
            active_alerts=[self._alert_read(item) for item in open_alerts],
            resolved_alerts=[self._alert_read(item) for item in resolved],
            last_analysis=self._run_read(last_ai or last_run) if (last_ai or last_run) else None,
            next_scheduled_at=next_at,
            disclaimer=PARCEL_INTELLIGENCE_DISCLAIMER,
            read_only=read_only,
        )

    def request_manual_analysis(self, owner_id: UUID, parcel_id: UUID) -> ParcelAnalysisRunRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        self.enqueue_event(
            parcel_id,
            ParcelAnalysisEventKind.MANUAL_REQUEST,
            {"source": "api"},
            process_inline=False,
        )
        run = self.process_parcel(parcel_id, force=True)
        return self._run_read(run)

    def acknowledge_alert(self, owner_id: UUID, alert_id: UUID) -> ParcelAlertRead:
        alert = self.repo.get_alert_for_owner(alert_id, owner_id)
        if alert is None:
            raise NotFoundError("Alert nije pronađen")
        if alert.status == ParcelAlertStatus.OPEN:
            alert.status = ParcelAlertStatus.ACKNOWLEDGED
            self.db.commit()
            self.db.refresh(alert)
        return self._alert_read(alert)

    def resolve_alert(self, owner_id: UUID, alert_id: UUID) -> ParcelAlertRead:
        alert = self.repo.get_alert_for_owner(alert_id, owner_id)
        if alert is None:
            raise NotFoundError("Alert nije pronađen")
        alert.status = ParcelAlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(alert)
        return self._alert_read(alert)

    def list_notifications(self, user_id: UUID) -> list[UserNotificationRead]:
        return [self._notification_read(item) for item in self.repo.list_notifications(user_id)]

    def process_pending(self, *, limit_parcels: int = 100) -> list[ParcelAnalysisRun]:
        if not self.settings.ai_intelligence_enabled:
            return []
        pending = self.repo.pending_events(limit=500)
        parcel_ids = []
        seen: set[UUID] = set()
        for event in pending:
            if event.parcel_id not in seen:
                seen.add(event.parcel_id)
                parcel_ids.append(event.parcel_id)
            if len(parcel_ids) >= limit_parcels:
                break
        runs: list[ParcelAnalysisRun] = []
        for parcel_id in parcel_ids:
            try:
                runs.append(self.process_parcel(parcel_id, force=False))
            except Exception:  # noqa: BLE001
                logger.exception("Intelligence process failed for parcel %s", parcel_id)
                self.db.rollback()
        return runs

    def process_scheduled(self) -> list[ParcelAnalysisRun]:
        if not self.settings.ai_intelligence_enabled:
            return []
        runs: list[ParcelAnalysisRun] = []
        for parcel in self.repo.parcels_for_scheduled():
            self.enqueue_event(parcel.id, ParcelAnalysisEventKind.SCHEDULED, {"source": "cron"})
            try:
                runs.append(self.process_parcel(parcel.id, force=False))
            except Exception:  # noqa: BLE001
                logger.exception("Scheduled intelligence failed for %s", parcel.id)
                self.db.rollback()
        return runs

    def process_parcel(self, parcel_id: UUID, *, force: bool = False) -> ParcelAnalysisRun:
        parcel = self.parcels.get_by_id(parcel_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")

        now = datetime.now(timezone.utc)
        pending = self.repo.pending_events(parcel_id)
        trigger_kinds = [event.kind.value for event in pending]
        if force and ParcelAnalysisEventKind.MANUAL_REQUEST.value not in trigger_kinds:
            trigger_kinds.append(ParcelAnalysisEventKind.MANUAL_REQUEST.value)

        history = self.satellites.list_for_parcel(parcel_id, limit=2, completed_only=True)
        latest_sat = history[0] if history else None
        previous_sat = history[1] if len(history) > 1 else None
        open_alerts = self.repo.open_alerts(parcel_id)
        last_ai = self.repo.latest_ai_run(parcel_id)

        recent_activities = self._recent_activities(parcel_id)
        recent_slugs = [
            item["semantic_type"] or item["activity_type_slug"]
            for item in recent_activities
            if item.get("semantic_type") or item.get("activity_type_slug")
        ]
        yield_dev = self._yield_deviation(parcel_id)

        change = detect_meaningful_changes(
            force=force,
            trigger_kinds=trigger_kinds,
            latest_satellite=sat_observation_summary(latest_sat),
            previous_satellite=sat_observation_summary(previous_sat),
            anomaly_count=int(latest_sat.anomaly_count) if latest_sat else 0,
            recent_activity_slugs=[s for s in recent_slugs if isinstance(s, str)],
            yield_deviation_percent=yield_dev,
            open_alert_count=len(open_alerts),
            last_analysis_at=last_ai.started_at if last_ai else None,
            min_interval_hours=float(self.settings.ai_analysis_min_interval_hours),
            ndvi_change_threshold=float(self.settings.ai_intelligence_ndvi_change_threshold),
        )

        context = self._build_context(
            parcel,
            latest_sat,
            previous_sat,
            open_alerts,
            recent_activities,
            yield_dev,
        )
        run = ParcelAnalysisRun(
            parcel_id=parcel_id,
            status=ParcelAnalysisRunStatus.SKIPPED,
            trigger_kinds=trigger_kinds,
            change_fingerprint=change.fingerprint,
            skip_reason=None if change.should_call_ai else change.reason,
            ai_called=False,
            context_snapshot=context,
            started_at=now,
        )
        self.repo.add_run(run)
        self.db.flush()

        if not change.should_call_ai:
            run.finished_at = datetime.now(timezone.utc)
            self.repo.mark_events_processed(pending, run_id=run.id, processed_at=run.finished_at)
            self.db.commit()
            self.db.refresh(run)
            return run

        try:
            result, raw, model = self._call_ai(trigger_kinds, change.signals, open_alerts, context)
            run.ai_called = True
            run.provider = self.provider.name
            run.model = model
            run.raw_response = raw
            run.validated_result = result.model_dump()
            run.status = ParcelAnalysisRunStatus.COMPLETED
            self._apply_ai_result(parcel, run, result, trigger_kinds)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            run.status = ParcelAnalysisRunStatus.FAILED
            run.error_message = f"Invalid AI JSON: {exc}"
            logger.warning("Invalid parcel intelligence JSON for %s: %s", parcel_id, exc)
        except Exception as exc:  # noqa: BLE001
            run.status = ParcelAnalysisRunStatus.FAILED
            run.error_message = str(exc)
            logger.exception("AI parcel intelligence failed for %s", parcel_id)

        run.finished_at = datetime.now(timezone.utc)
        self.repo.mark_events_processed(pending, run_id=run.id, processed_at=run.finished_at)
        self.db.commit()
        self.db.refresh(run)
        return run

    # --- AI ---

    def _call_ai(self, trigger_kinds, signals, open_alerts, context: dict) -> tuple[ParcelIntelligenceAIResult, dict, str | None]:
        changes_text = "\n".join(f"- [{s.severity_hint}] {s.description}" for s in signals) or "- (none)"
        open_text = "\n".join(f"- [{a.severity.value}] {a.issue_key}: {a.title}" for a in open_alerts) or "- none"
        user = PARCEL_INTELLIGENCE_USER_TEMPLATE.format(
            trigger=", ".join(trigger_kinds) or "unknown",
            changes=changes_text,
            open_alerts=open_text,
            context=json.dumps(context, ensure_ascii=False, default=str),
            disclaimer=PARCEL_INTELLIGENCE_DISCLAIMER,
        )
        chat = self.provider.chat(
            [
                ChatMessage(role="system", content=PARCEL_INTELLIGENCE_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user),
            ],
            json_mode=True,
            temperature=0.1,
        )
        raw = _parse_json_object(chat.content)
        result = ParcelIntelligenceAIResult.model_validate(raw)
        return result, raw, chat.model

    def _apply_ai_result(
        self,
        parcel: Parcel,
        run: ParcelAnalysisRun,
        result: ParcelIntelligenceAIResult,
        trigger_kinds: list[str],
    ) -> None:
        # OK must not auto-resolve unrelated alerts — only the user resolves explicitly.
        if result.status == "OK":
            return

        issue_key = result.issue_key or _default_issue_key(result)
        severity = ParcelAlertSeverity(result.status)
        evidence = self._evidence_with_trees(parcel.id, result)
        result = self._humanize_result_text(result, evidence)
        existing = self.repo.find_open_alert(parcel.id, issue_key)
        if existing is not None:
            escalated = _SEVERITY_RANK[severity] > _SEVERITY_RANK[existing.severity]
            material = _evidence_materially_changed(existing, result, evidence)
            if escalated or material:
                if escalated:
                    existing.severity = severity
                existing.title = result.title
                existing.summary = result.summary
                existing.observed_facts = result.observed_facts
                existing.possible_causes = result.possible_causes
                existing.recommended_actions = result.recommended_actions
                existing.confidence = Decimal(str(result.confidence))
                existing.evidence = evidence
                existing.analysis_run_id = run.id
                existing.source_events = list({*existing.source_events, *trigger_kinds})
                if escalated:
                    self._maybe_notify(parcel, existing, result, escalated=True)
            return

        alert = ParcelAlert(
            parcel_id=parcel.id,
            severity=severity,
            status=ParcelAlertStatus.OPEN,
            issue_key=issue_key,
            title=result.title,
            summary=result.summary,
            observed_facts=result.observed_facts,
            possible_causes=result.possible_causes,
            recommended_actions=result.recommended_actions,
            source_events=list(trigger_kinds),
            confidence=Decimal(str(result.confidence)),
            evidence=evidence,
            analysis_run_id=run.id,
        )
        self.repo.add_alert(alert)
        self.db.flush()
        self._maybe_notify(parcel, alert, result, escalated=False)

    def _maybe_notify(
        self,
        parcel: Parcel,
        alert: ParcelAlert,
        result: ParcelIntelligenceAIResult,
        *,
        escalated: bool,
    ) -> None:
        should = result.should_notify or alert.severity in {
            ParcelAlertSeverity.WARNING,
            ParcelAlertSeverity.CRITICAL,
        }
        if alert.severity == ParcelAlertSeverity.INFO and not result.should_notify:
            return
        if not should:
            return
        farm = self.db.get(Farm, parcel.farm_id)
        if farm is None:
            return
        title_prefix = "Eskalacija: " if escalated else ""
        self.repo.add_notification(
            UserNotification(
                user_id=farm.owner_id,
                parcel_id=parcel.id,
                alert_id=alert.id,
                severity=alert.severity.value,
                title=f"{title_prefix}{alert.title}",
                body=alert.summary,
                payload={
                    "issue_key": alert.issue_key,
                    "observed_facts": alert.observed_facts,
                    "possible_causes": alert.possible_causes,
                    "recommended_actions": alert.recommended_actions,
                },
            )
        )

    # --- context ---

    def _build_context(
        self,
        parcel: Parcel,
        latest_sat,
        previous_sat,
        open_alerts: list[ParcelAlert],
        recent_activities: list[dict[str, Any]],
        yield_dev: Decimal | None,
    ) -> dict[str, Any]:
        age = None
        if parcel.default_planting_year:
            age = datetime.now(timezone.utc).year - parcel.default_planting_year + 1
        parcel_trees = [tree for tree, _row in self.trees.list_map_for_parcel(parcel.id)]
        boundary = parcel.boundary if isinstance(parcel.boundary, dict) else None
        zone_anomalies = serialize_zone_anomalies(
            latest_sat,
            trees=parcel_trees,
            parcel_boundary=boundary,
        )
        return {
            "parcel": {
                "id": str(parcel.id),
                "name": parcel.name,
                "area_hectares": str(parcel.area_hectares) if parcel.area_hectares is not None else None,
                "has_boundary": bool(parcel.boundary),
                "latitude": str(parcel.latitude) if parcel.latitude is not None else None,
                "longitude": str(parcel.longitude) if parcel.longitude is not None else None,
                "default_variety": parcel.default_variety,
                "varieties": parcel.varieties,
                "planting_year": parcel.default_planting_year,
                "orchard_age_year": age,
                "production_method": parcel.production_method.value if parcel.production_method else None,
                "has_irrigation": parcel.has_irrigation,
            },
            "satellite_latest": sat_observation_summary(latest_sat),
            "satellite_previous": sat_observation_summary(previous_sat),
            "satellite_zone_anomalies": zone_anomalies,
            "satellite_anomaly_threshold_notes": [
                "Zone anomalies use relative NDVI thresholds only "
                f"(below_parcel_mean fraction={self.settings.satellite_anomaly_below_mean_fraction}, "
                f"sudden_decline fraction={self.settings.satellite_anomaly_sudden_decline_fraction}).",
                "NDRE and NDWI are stored for context/maps but are not used by the zone anomaly detector.",
                "Index thresholds are anomaly signals, not disease/drought diagnoses.",
                "Prefer tree_public_ids (e.g. R03-T0012) when describing where the problem is. "
                "Do not mention internal grid keys like r3c0 to the farmer.",
            ],
            "weather": self._weather_context(parcel.id),
            "soil": self._soil_context(parcel.id),
            "recent_activities": recent_activities,
            "recent_observations": self._recent_disease_cases(parcel.id),
            "yield_deviation_percent": str(yield_dev) if yield_dev is not None else None,
            "open_alerts": [
                {
                    "issue_key": a.issue_key,
                    "severity": a.severity.value,
                    "title": a.title,
                    "summary": a.summary,
                    "zone_keys": list((a.evidence or {}).get("zone_keys") or []),
                    "tree_public_ids": list((a.evidence or {}).get("tree_public_ids") or []),
                }
                for a in open_alerts
            ],
            "data_notes": [
                "Only listed fields are available. Do not invent missing soil/weather/satellite values.",
                "possible_causes must remain hypotheses.",
                "Forecast weather is not an observation of past rainfall on the parcel.",
                "Missing fields are null or empty lists — treat as unavailable.",
            ],
        }

    def _evidence_with_trees(self, parcel_id: UUID, result: ParcelIntelligenceAIResult) -> dict[str, Any]:
        evidence = _evidence_from_result(result)
        tree_ids = list(result.tree_public_ids or [])
        history = self.satellites.list_for_parcel(parcel_id, limit=1, completed_only=True)
        latest = history[0] if history else None
        parcel = self.parcels.get_by_id(parcel_id)
        boundary = parcel.boundary if parcel is not None and isinstance(parcel.boundary, dict) else None
        parcel_trees = [tree for tree, _row in self.trees.list_map_for_parcel(parcel_id)]
        mapping = zone_tree_map(
            getattr(latest, "zones", None) or [],
            parcel_trees,
            parcel_boundary=boundary,
        )
        if not tree_ids and result.zone_keys and latest is not None:
            tree_ids = trees_for_zone_keys(
                zone_keys=result.zone_keys,
                zones=getattr(latest, "zones", None) or [],
                trees=parcel_trees,
                parcel_boundary=boundary,
            )
        evidence["tree_public_ids"] = tree_ids
        evidence["_zone_tree_map"] = mapping  # used while rewriting, stripped before persist
        return evidence

    def _humanize_result_text(
        self,
        result: ParcelIntelligenceAIResult,
        evidence: dict[str, Any],
    ) -> ParcelIntelligenceAIResult:
        mapping = evidence.pop("_zone_tree_map", {}) or {}
        trees = list(evidence.get("tree_public_ids") or [])
        return result.model_copy(
            update={
                "title": rewrite_zone_keys_in_text(result.title, mapping, fallback_trees=trees),
                "summary": rewrite_zone_keys_in_text(result.summary, mapping, fallback_trees=trees),
                "observed_facts": rewrite_zone_keys_in_strings(
                    result.observed_facts, mapping, fallback_trees=trees
                ),
                "possible_causes": rewrite_zone_keys_in_strings(
                    result.possible_causes, mapping, fallback_trees=trees
                ),
                "recommended_actions": rewrite_zone_keys_in_strings(
                    result.recommended_actions, mapping, fallback_trees=trees
                ),
                "tree_public_ids": trees,
            }
        )

    def _weather_context(self, parcel_id: UUID) -> dict[str, Any]:
        cache = self.weather_cache.get_for_parcel(parcel_id)
        if cache is None:
            return {
                "available": False,
                "status": "missing",
                "source": "Yr",
                "message": "Nema keširane prognoze za parcelu.",
                "forecast_days": [],
            }
        normalized = cache.normalized_response if isinstance(cache.normalized_response, dict) else {}
        days_raw = normalized.get("forecast") if isinstance(normalized.get("forecast"), list) else []
        days: list[dict[str, Any]] = []
        for day in days_raw[:7]:
            if not isinstance(day, dict):
                continue
            days.append(
                {
                    "date": day.get("date"),
                    "min_temperature": day.get("min_temperature"),
                    "max_temperature": day.get("max_temperature"),
                    "precipitation": day.get("precipitation"),
                    "precipitation_probability": day.get("precipitation_probability"),
                    "symbol_code": day.get("symbol_code"),
                }
            )
        precip_total = 0.0
        for day in days:
            try:
                precip_total += float(day.get("precipitation") or 0)
            except (TypeError, ValueError):
                continue
        temps = [
            float(v)
            for day in days
            for v in (day.get("min_temperature"), day.get("max_temperature"))
            if v is not None and _is_finite_float(v)
        ]
        return {
            "available": True,
            "status": "cached_forecast",
            "source": cache.provider or "Yr",
            "forecast_date": cache.forecast_date.isoformat() if cache.forecast_date else None,
            "fetched_at": cache.fetched_at.isoformat() if cache.fetched_at else None,
            "note": "Cached Yr forecast (not historical weather observations).",
            "precipitation_sum_next_days": round(precip_total, 2) if days else None,
            "temperature_min": min(temps) if temps else None,
            "temperature_max": max(temps) if temps else None,
            "forecast_days": days,
        }

    def _soil_context(self, parcel_id: UUID) -> dict[str, Any]:
        verified = self.soil_lab.get_latest_verified(parcel_id)
        if verified is None:
            return {
                "available": False,
                "status": "missing",
                "message": "Nema verifikovane laboratorijske analize zemljišta.",
            }
        return {
            "available": True,
            "status": "verified_lab",
            "sampled_on": verified.sampled_on.isoformat()
            if getattr(verified, "sampled_on", None)
            else None,
            "laboratory_name": getattr(verified, "laboratory_name", None),
            "result_summary": _soil_result_summary(verified),
        }

    def _recent_activities(self, parcel_id: UUID) -> list[dict[str, Any]]:
        since = datetime.now(timezone.utc).date() - timedelta(days=30)
        items = list(
            self.db.scalars(
                select(Activity)
                .where(Activity.parcel_id == parcel_id, Activity.performed_on >= since)
                .options(selectinload(Activity.activity_type))
                .order_by(Activity.performed_on.desc())
                .limit(15)
            ).all()
        )
        out: list[dict[str, Any]] = []
        for activity in items:
            semantic = getattr(activity, "semantic_type", None)
            atype = getattr(activity, "activity_type", None)
            out.append(
                {
                    "performed_on": activity.performed_on.isoformat()
                    if activity.performed_on
                    else None,
                    "title": activity.title,
                    "semantic_type": semantic.value if semantic else None,
                    "activity_type_slug": getattr(atype, "slug", None),
                    "activity_type_name": getattr(atype, "name", None),
                    "notes": (activity.notes[:240] if activity.notes else None),
                    "quantity": str(activity.quantity) if activity.quantity is not None else None,
                    "unit": activity.unit,
                }
            )
        return out

    def _recent_disease_cases(self, parcel_id: UUID) -> list[dict[str, Any]]:
        items = list(
            self.db.scalars(
                select(DiseaseCase)
                .where(
                    DiseaseCase.parcel_id == parcel_id,
                    DiseaseCase.status != DiseaseCaseStatus.RESOLVED,
                )
                .order_by(DiseaseCase.detected_on.desc())
                .limit(8)
            ).all()
        )
        return [
            {
                "id": str(item.id),
                "title": item.title,
                "category": item.category.value if hasattr(item.category, "value") else str(item.category),
                "severity": item.severity.value if hasattr(item.severity, "value") else str(item.severity),
                "status": item.status.value if hasattr(item.status, "value") else str(item.status),
                "detected_on": item.detected_on.isoformat() if item.detected_on else None,
            }
            for item in items
        ]

    def _yield_deviation(self, parcel_id: UUID) -> Decimal | None:
        # Soft integration: if production expected_yield is expensive, skip unless easy.
        del parcel_id
        return None

    def _alert_read(self, item: ParcelAlert) -> ParcelAlertRead:
        evidence = dict(item.evidence or {})
        title = item.title
        summary = item.summary
        observed = list(item.observed_facts or [])
        causes = list(item.possible_causes or [])
        actions = list(item.recommended_actions or [])
        tree_ids = [
            str(value).strip().upper()
            for value in (evidence.get("tree_public_ids") or [])
            if isinstance(value, str) and value.strip()
        ]
        zone_keys = [
            str(value)
            for value in (evidence.get("zone_keys") or [])
            if isinstance(value, str) and value.strip()
        ]
        needs_rewrite = any(
            _ZONE_KEY_RE.search(text or "")
            for text in [title, summary, *observed, *causes, *actions]
        )
        if needs_rewrite or (zone_keys and not tree_ids):
            history = self.satellites.list_for_parcel(item.parcel_id, limit=1, completed_only=True)
            latest = history[0] if history else None
            parcel = self.parcels.get_by_id(item.parcel_id)
            boundary = (
                parcel.boundary if parcel is not None and isinstance(parcel.boundary, dict) else None
            )
            parcel_trees = [tree for tree, _row in self.trees.list_map_for_parcel(item.parcel_id)]
            mapping = zone_tree_map(
                getattr(latest, "zones", None) or [],
                parcel_trees,
                parcel_boundary=boundary,
            )
            if not tree_ids and zone_keys and latest is not None:
                tree_ids = trees_for_zone_keys(
                    zone_keys=zone_keys,
                    zones=getattr(latest, "zones", None) or [],
                    trees=parcel_trees,
                    parcel_boundary=boundary,
                )
            evidence["tree_public_ids"] = tree_ids
            title = rewrite_zone_keys_in_text(title, mapping, fallback_trees=tree_ids)
            summary = rewrite_zone_keys_in_text(summary, mapping, fallback_trees=tree_ids)
            observed = rewrite_zone_keys_in_strings(observed, mapping, fallback_trees=tree_ids)
            causes = rewrite_zone_keys_in_strings(causes, mapping, fallback_trees=tree_ids)
            actions = rewrite_zone_keys_in_strings(actions, mapping, fallback_trees=tree_ids)
        return ParcelAlertRead(
            id=item.id,
            parcel_id=item.parcel_id,
            severity=item.severity.value,
            status=item.status.value,
            issue_key=item.issue_key,
            title=title,
            summary=summary,
            observed_facts=observed,
            possible_causes=causes,
            recommended_actions=actions,
            source_events=list(item.source_events or []),
            confidence=item.confidence,
            evidence=evidence,
            created_at=item.created_at,
            resolved_at=item.resolved_at,
        )

    def _run_read(self, item: ParcelAnalysisRun) -> ParcelAnalysisRunRead:
        return ParcelAnalysisRunRead(
            id=item.id,
            parcel_id=item.parcel_id,
            status=item.status.value,
            ai_called=item.ai_called,
            skip_reason=item.skip_reason,
            trigger_kinds=list(item.trigger_kinds or []),
            provider=item.provider,
            model=item.model,
            validated_result=item.validated_result,
            error_message=item.error_message,
            started_at=item.started_at,
            finished_at=item.finished_at,
        )

    def _notification_read(self, item: UserNotification) -> UserNotificationRead:
        return UserNotificationRead(
            id=item.id,
            parcel_id=item.parcel_id,
            alert_id=item.alert_id,
            severity=item.severity,
            title=item.title,
            body=item.body,
            read_at=item.read_at,
            created_at=item.created_at,
            payload=dict(item.payload or {}),
        )


def _parse_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("AI response is not a JSON object")
    return payload


def _default_issue_key(result: ParcelIntelligenceAIResult) -> str:
    base = result.title.lower().replace(" ", "_")[:40]
    return f"{result.status.lower()}_{base}" or "general_issue"


def _evidence_from_result(result: ParcelIntelligenceAIResult) -> dict[str, Any]:
    return {
        "zone_keys": list(result.zone_keys or []),
        "tree_public_ids": list(result.tree_public_ids or []),
        "affected_indices": list(result.affected_indices or []),
        "observation_date": result.observation_date,
        "data_quality_notes": list(result.data_quality_notes or []),
    }


def _evidence_materially_changed(
    existing: ParcelAlert,
    result: ParcelIntelligenceAIResult,
    evidence: dict[str, Any],
) -> bool:
    if existing.summary != result.summary:
        return True
    if list(existing.observed_facts or []) != list(result.observed_facts or []):
        return True
    if list(existing.possible_causes or []) != list(result.possible_causes or []):
        return True
    if list(existing.recommended_actions or []) != list(result.recommended_actions or []):
        return True
    prev = existing.evidence if isinstance(existing.evidence, dict) else {}
    if sorted(prev.get("zone_keys") or []) != sorted(evidence.get("zone_keys") or []):
        return True
    if sorted(prev.get("tree_public_ids") or []) != sorted(evidence.get("tree_public_ids") or []):
        return True
    if sorted(prev.get("affected_indices") or []) != sorted(evidence.get("affected_indices") or []):
        return True
    if prev.get("observation_date") != evidence.get("observation_date"):
        return True
    return False


def _is_finite_float(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _soil_result_summary(analysis) -> dict[str, Any] | None:
    results = list(getattr(analysis, "results", None) or [])
    if not results:
        return None
    compact: dict[str, Any] = {}
    for item in results[:12]:
        code = getattr(item, "parameter_code", None) or getattr(item, "parameter_name", None)
        if not code:
            continue
        compact[str(code)] = {
            "value": str(item.value) if getattr(item, "value", None) is not None else None,
            "unit": getattr(item, "unit", None),
        }
    return compact or {"parameter_count": len(results)}
