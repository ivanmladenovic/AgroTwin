"""Satellite monitoring orchestration (provider-agnostic)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.geojson import validate_boundary_geojson
from app.models.enums import SatelliteProcessingStatus
from app.models.parcel import Parcel
from app.models.satellite import SatelliteAnomaly, SatelliteObservation, SatelliteZoneMetric
from app.repositories.parcel import ParcelRepository
from app.repositories.satellite import SatelliteRepository
from app.repositories.tree import TreeRepository
from app.services.orchard import OrchardService
from app.satellite.anomalies import ZoneSnapshot, detect_anomalies
from app.satellite.history import build_satellite_history
from app.satellite.indices import (
    DISPLAY_RESOLUTION_M,
    INDEX_FORMULAS,
    INDEX_NATIVE_RESOLUTION,
    IndexName,
    decimal_or_none,
)
from app.satellite.providers.base import (
    IndexCalculationResult,
    IndexStatistics,
    SatelliteProvider,
    SatelliteProviderError,
)
from app.satellite.providers.factory import get_satellite_provider
from app.satellite.selection import select_best_image
from app.satellite.zone_trees import trees_in_zone_geometry
from app.satellite.zones import build_zone_grid, point_in_geometry
from app.schemas.satellite import (
    ParcelSatelliteMonitoringRead,
    SatelliteAnomalyRead,
    SatelliteHistoryRead,
    SatelliteChangeRead,
    SatelliteDataCapabilities,
    SatelliteObservationRead,
    SatelliteObservationSummary,
    SatelliteSampleRead,
    SatelliteSyncResultRead,
    SatelliteZoneRead,
    VisualizationLayerRead,
)
from app.storage import get_storage

logger = logging.getLogger(__name__)


class SatelliteService:
    def __init__(
        self,
        db: Session,
        provider: SatelliteProvider | None = None,
    ) -> None:
        self.db = db
        self.parcels = ParcelRepository(db)
        self.repo = SatelliteRepository(db)
        self.trees = TreeRepository(db)
        self.provider = provider or get_satellite_provider()
        self.settings = get_settings()

    def get_monitoring(self, owner_id: UUID, parcel_id: UUID) -> ParcelSatelliteMonitoringRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")

        history = self.repo.list_for_parcel(parcel_id, limit=40, completed_only=True)
        latest = history[0] if history else None
        previous = history[1] if len(history) > 1 else None

        if not parcel.boundary:
            if OrchardService(self.db).ensure_approximate_boundary(parcel):
                self.db.commit()
                self.db.refresh(parcel)
            else:
                return ParcelSatelliteMonitoringRead(
                    parcel_id=parcel_id,
                    available=False,
                    status="boundary_required",
                    message=(
                        "Za satelitski monitoring potrebna je granica parcele. "
                        "Dodajte Google Maps link i površinu (ha) na izmeni parcele — "
                        "sistem će napraviti približan kvadrat oko pin-a."
                    ),
                    provider=self.provider.name,
                    index_formulas=INDEX_FORMULAS,
                    capabilities=self._capabilities(parcel, None),
                    history=[],
                )

        if latest is None:
            return ParcelSatelliteMonitoringRead(
                parcel_id=parcel_id,
                available=False,
                status="no_observations",
                message=(
                    "Još nema obrađenih satelitskih opservacija. "
                    "Kliknite „Osveži snimak“ da povučete Sentinel-2 sa Copernicus-a."
                ),
                provider=self.provider.name,
                index_formulas=INDEX_FORMULAS,
                capabilities=self._capabilities(parcel, None),
                history=[],
            )

        self._ensure_visualizations(parcel, latest)
        self.db.refresh(latest)

        anomalies = [
            self._anomaly_read(item)
            for item in (latest.anomalies or [])
        ]
        observation = self._observation_read(latest)
        return ParcelSatelliteMonitoringRead(
            parcel_id=parcel_id,
            available=True,
            status="ok",
            message=None,
            provider=self.provider.name,
            index_formulas=dict(latest.index_formulas or INDEX_FORMULAS),
            capabilities=self._capabilities(parcel, observation),
            latest=observation,
            previous=self._observation_read(previous) if previous else None,
            changes=self._changes(latest, previous),
            history=[self._summary(item) for item in history],
            anomalies=anomalies,
        )

    def get_history(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> SatelliteHistoryRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return self.history_for_parcel(parcel_id, date_from=date_from, date_to=date_to)

    def history_for_parcel(
        self,
        parcel_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> SatelliteHistoryRead:
        """Read stored observations only. Does not refresh or call the provider."""
        if date_from and date_to and date_from > date_to:
            date_from, date_to = date_to, date_from
        observations = self.repo.list_for_parcel(parcel_id, limit=400, completed_only=True)
        payload = build_satellite_history(
            observations,
            parcel_id=parcel_id,
            date_from=date_from,
            date_to=date_to,
        )
        return SatelliteHistoryRead.model_validate(payload)

    def list_observations(self, owner_id: UUID, parcel_id: UUID) -> list[SatelliteObservationSummary]:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return [
            self._summary(item)
            for item in self.repo.list_for_parcel(parcel_id, limit=100, completed_only=False)
        ]

    def get_observation(self, owner_id: UUID, observation_id: UUID) -> SatelliteObservationRead:
        observation = self.repo.get_for_owner(observation_id, owner_id)
        if observation is None:
            raise NotFoundError("Satelitska opservacija nije pronađena")
        parcel = self.parcels.get_for_owner(observation.parcel_id, owner_id)
        if parcel is not None:
            self._ensure_visualizations(parcel, observation)
            self.db.refresh(observation)
        return self._observation_read(observation)

    def get_visualization_bytes(
        self,
        owner_id: UUID,
        observation_id: UUID,
        index: str,
    ) -> tuple[bytes, str]:
        observation = self.repo.get_for_owner(observation_id, owner_id)
        if observation is None:
            raise NotFoundError("Satelitska opservacija nije pronađena")
        parcel = self.parcels.get_for_owner(observation.parcel_id, owner_id)
        if parcel is not None:
            self._ensure_visualizations(parcel, observation)
            self.db.refresh(observation)
        meta = (observation.source_metadata or {}).get("visualization_layers") or {}
        layer = meta.get(index) if isinstance(meta, dict) else None
        if not isinstance(layer, dict) or not layer.get("storage_key"):
            raise NotFoundError("Vizualizacija nije dostupna")
        storage = get_storage()
        try:
            content = storage.get(str(layer["storage_key"]))
        except FileNotFoundError as exc:
            raise NotFoundError("Vizualizacija nije dostupna") from exc
        content_type = str(layer.get("content_type") or "image/png")
        return content, content_type

    def refresh_parcel(self, owner_id: UUID, parcel_id: UUID) -> SatelliteSyncResultRead:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return self.process_parcel(parcel)

    def process_all_parcels(self) -> list[SatelliteSyncResultRead]:
        if not self.settings.satellite_enabled:
            return []
        results: list[SatelliteSyncResultRead] = []
        for parcel in self.repo.list_parcels_with_boundary():
            try:
                results.append(self.process_parcel(parcel))
            except Exception as exc:  # noqa: BLE001 — job must continue across parcels
                logger.exception("Satellite sync failed for parcel %s", parcel.id)
                self.db.rollback()
                results.append(
                    SatelliteSyncResultRead(
                        parcel_id=parcel.id,
                        status="failed",
                        message=str(exc),
                    )
                )
        return results

    def process_parcel(self, parcel: Parcel) -> SatelliteSyncResultRead:
        if not self.settings.satellite_enabled:
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="skipped",
                message="Satellite monitoring is disabled",
            )
        if not parcel.boundary:
            if OrchardService(self.db).ensure_approximate_boundary(parcel):
                self.db.flush()
            else:
                return SatelliteSyncResultRead(
                    parcel_id=parcel.id,
                    status="skipped",
                    message="Parcel boundary is missing (need Maps pin + area, or GeoJSON polygon)",
                )
        try:
            geometry = validate_boundary_geojson(parcel.boundary)
        except Exception as exc:  # noqa: BLE001
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="failed",
                message=f"Invalid parcel boundary: {exc}",
            )

        end_date = date.today()
        start_date = end_date - timedelta(days=self.settings.satellite_lookback_days)
        thresholds = self._cloud_thresholds()

        try:
            candidate, threshold = select_best_image(
                self.provider,
                geometry,
                start_date,
                end_date,
                cloud_thresholds=thresholds,
                absolute_max_cloud=self.settings.satellite_absolute_max_cloud,
            )
        except SatelliteProviderError as exc:
            return self._record_failure(
                parcel,
                product_id=f"search-failed-{end_date.isoformat()}",
                message=exc.message,
            )

        if candidate is None:
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="skipped",
                message="No valid Sentinel-2 image found in the lookback window",
            )

        existing = self.repo.get_by_product(parcel.id, self.provider.name, candidate.product_id)
        if (
            existing is not None
            and existing.processing_status == SatelliteProcessingStatus.COMPLETED
            and not self._zone_indices_incomplete(existing)
        ):
            # Force regen so a newly drawn boundary re-clips rasters to the new geometry.
            self._ensure_visualizations(parcel, existing, force=True)
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="skipped",
                message="Observation already processed",
                observation_id=existing.id,
                skipped_duplicate=True,
            )

        observation = existing or SatelliteObservation(
            parcel_id=parcel.id,
            provider=self.provider.name,
            satellite=candidate.satellite,
            product_id=candidate.product_id,
            acquisition_date=candidate.acquisition_date,
            acquisition_at=candidate.acquisition_at,
            cloud_cover=decimal_or_none(candidate.cloud_cover, "0.01"),
            requested_cloud_threshold=decimal_or_none(threshold, "0.01"),
            processing_status=SatelliteProcessingStatus.PROCESSING,
            visualization_refs={},
            source_metadata={},
            index_formulas=dict(INDEX_FORMULAS),
        )
        if existing is None:
            self.repo.add_observation(observation)
        else:
            observation.processing_status = SatelliteProcessingStatus.PROCESSING
            observation.error_message = None
        self.db.commit()
        self.db.refresh(observation)

        try:
            zones = build_zone_grid(
                geometry,
                grid_size=self.settings.satellite_zone_grid_size,
            )
            result = self.provider.calculate_indices(
                geometry,
                candidate.image_id,
                [IndexName.NDVI, IndexName.NDRE, IndexName.NDWI],
                zone_geometries=zones,
            )
            self._persist_success(observation, result, threshold)
            self.db.commit()
            self.db.refresh(observation)
            self._ensure_visualizations(parcel, observation, force=True)
            self.db.refresh(observation)
            self._enqueue_intelligence(parcel.id, observation.anomaly_count)
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="completed",
                observation_id=observation.id,
                message=None,
            )
        except SatelliteProviderError as exc:
            observation.processing_status = SatelliteProcessingStatus.FAILED
            observation.error_message = exc.message
            observation.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="failed",
                observation_id=observation.id,
                message=exc.message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected satellite processing error for %s", parcel.id)
            observation.processing_status = SatelliteProcessingStatus.FAILED
            observation.error_message = str(exc)
            observation.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            return SatelliteSyncResultRead(
                parcel_id=parcel.id,
                status="failed",
                observation_id=observation.id,
                message=str(exc),
            )

    def _persist_success(
        self,
        observation: SatelliteObservation,
        result: IndexCalculationResult,
        threshold: float | None,
    ) -> None:
        observation.processing_status = SatelliteProcessingStatus.COMPLETED
        observation.error_message = None
        observation.processed_at = datetime.now(timezone.utc)
        observation.acquisition_date = result.acquisition_date
        observation.acquisition_at = result.acquisition_at
        observation.cloud_cover = decimal_or_none(result.cloud_cover, "0.01")
        observation.requested_cloud_threshold = decimal_or_none(threshold, "0.01")
        observation.image_reference = result.image_reference
        observation.visualization_refs = dict(result.visualization_refs or {})
        metadata = dict(result.metadata or {})
        metadata["valid_pixel_counts"] = {
            "ndvi": int(result.ndvi.valid_pixel_count or 0),
            "ndre": int(result.ndre.valid_pixel_count or 0),
            "ndwi": int(result.ndwi.valid_pixel_count or 0),
        }
        observation.source_metadata = metadata
        observation.index_formulas = dict(INDEX_FORMULAS)
        observation.satellite = result.satellite

        self._apply_stats(observation, "ndvi", result.ndvi)
        self._apply_stats(observation, "ndre", result.ndre)
        self._apply_stats(observation, "ndwi", result.ndwi)

        # Replace zones / anomalies
        observation.zones.clear()
        observation.anomalies.clear()
        self.db.flush()

        zone_snapshots: list[ZoneSnapshot] = []
        for zone in result.zones:
            ndvi_mean = decimal_or_none(zone.ndvi.mean if zone.ndvi else None)
            ndre_mean = decimal_or_none(zone.ndre.mean if zone.ndre else None)
            ndwi_mean = decimal_or_none(zone.ndwi.mean if zone.ndwi else None)
            deviation = None
            if ndvi_mean is not None and observation.ndvi_mean is not None:
                deviation = (ndvi_mean - observation.ndvi_mean).quantize(Decimal("0.0001"))
            self.repo.add_zone(
                SatelliteZoneMetric(
                    observation_id=observation.id,
                    zone_key=zone.zone_key,
                    geometry=zone.geometry,
                    ndvi=ndvi_mean,
                    ndre=ndre_mean,
                    ndwi=ndwi_mean,
                    ndvi_deviation=deviation,
                )
            )
            zone_snapshots.append(
                ZoneSnapshot(
                    zone_key=zone.zone_key,
                    ndvi=ndvi_mean,
                    ndre=ndre_mean,
                    ndwi=ndwi_mean,
                )
            )

        previous = self.repo.list_for_parcel(
            observation.parcel_id, limit=3, completed_only=True
        )
        # Exclude the observation currently being written if it already appears.
        previous = [item for item in previous if item.id != observation.id]
        prev_zones = [
            ZoneSnapshot(zone_key=z.zone_key, ndvi=z.ndvi, ndre=z.ndre, ndwi=z.ndwi)
            for z in (previous[0].zones if previous else [])
        ]
        prev2_zones = [
            ZoneSnapshot(zone_key=z.zone_key, ndvi=z.ndvi, ndre=z.ndre, ndwi=z.ndwi)
            for z in (previous[1].zones if len(previous) > 1 else [])
        ]
        findings = detect_anomalies(
            parcel_ndvi_mean=observation.ndvi_mean,
            current_zones=zone_snapshots,
            previous_zones=prev_zones,
            previous_previous_zones=prev2_zones,
            below_mean_fraction=self.settings.satellite_anomaly_below_mean_fraction,
            sudden_decline_fraction=self.settings.satellite_anomaly_sudden_decline_fraction,
        )
        for finding in findings:
            self.repo.add_anomaly(
                SatelliteAnomaly(
                    observation_id=observation.id,
                    parcel_id=observation.parcel_id,
                    zone_key=finding.zone_key,
                    kind=finding.kind,
                    index_name=finding.index_name,
                    severity=Decimal(str(round(finding.severity, 4))),
                    message=finding.message,
                    details=finding.details,
                )
            )
        observation.anomaly_count = len(findings)

    def _apply_stats(
        self,
        observation: SatelliteObservation,
        prefix: str,
        stats: IndexStatistics,
    ) -> None:
        setattr(observation, f"{prefix}_mean", decimal_or_none(stats.mean))
        setattr(observation, f"{prefix}_min", decimal_or_none(stats.min))
        setattr(observation, f"{prefix}_max", decimal_or_none(stats.max))
        if prefix == "ndvi":
            observation.ndvi_stddev = decimal_or_none(stats.stddev)

    def _record_failure(
        self,
        parcel: Parcel,
        *,
        product_id: str,
        message: str,
    ) -> SatelliteSyncResultRead:
        # Do not invent a fake product row for every search failure; keep dashboard intact.
        logger.warning("Satellite search failed for parcel %s: %s", parcel.id, message)
        return SatelliteSyncResultRead(
            parcel_id=parcel.id,
            status="failed",
            message=message,
        )

    def _capabilities(
        self,
        parcel: Parcel,
        observation: SatelliteObservationRead | None,
    ) -> SatelliteDataCapabilities:
        has_zones = bool(observation and observation.zones)
        has_agg = bool(
            observation
            and (
                observation.ndvi_mean is not None
                or observation.ndre_mean is not None
                or observation.ndwi_mean is not None
            )
        )
        has_raster = bool(
            observation
            and (
                (observation.visualization_layers and len(observation.visualization_layers) > 0)
                or (
                    isinstance(observation.visualization_refs, dict)
                    and any(
                        key in {"ndvi", "ndre", "ndwi"}
                        and str(value).startswith(("http://", "https://", "/"))
                        for key, value in observation.visualization_refs.items()
                    )
                )
            )
        )
        if has_raster:
            note = (
                "Analitički sloj je georeferencirani Sentinel-2 PNG isečen na granicu parcele. "
                f"Prikaz ~{DISPLAY_RESOLUTION_M:g} m je samo vizuelni upsample — nativna rezolucija "
                "indeksa zavisi od traka (NDVI ~10 m, NDRE ~20 m, NDWI 10–20 m)."
            )
        elif has_zones:
            note = (
                "Zone su mreža nad poligonom parcele; vrednosti su prostorni proseci "
                "(nije kontinuirani piksel-raster)."
            )
        else:
            note = None
        return SatelliteDataCapabilities(
            has_boundary=parcel.boundary is not None,
            has_centroid=parcel.latitude is not None and parcel.longitude is not None,
            has_aggregate_indices=has_agg,
            has_zone_statistics=has_zones,
            has_index_raster=has_raster,
            has_anomalies=bool(observation and observation.anomaly_count > 0),
            spatial_resolution_note=note,
            sensor="Sentinel-2 L2A",
            display_resolution_m=float(DISPLAY_RESOLUTION_M),
            native_resolutions=dict(INDEX_NATIVE_RESOLUTION),
        )

    def _cloud_thresholds(self) -> tuple[float, ...]:
        raw = self.settings.satellite_cloud_thresholds or "20,30,40"
        values: list[float] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            values.append(float(part))
        return tuple(values) or (20.0, 30.0, 40.0)

    def _changes(
        self,
        latest: SatelliteObservation,
        previous: SatelliteObservation | None,
    ) -> list[SatelliteChangeRead]:
        if previous is None:
            return []
        changes: list[SatelliteChangeRead] = []
        for name, latest_val, prev_val in (
            ("ndvi", latest.ndvi_mean, previous.ndvi_mean),
            ("ndre", latest.ndre_mean, previous.ndre_mean),
            ("ndwi", latest.ndwi_mean, previous.ndwi_mean),
        ):
            pct = None
            if latest_val is not None and prev_val is not None and prev_val != 0:
                pct = ((latest_val - prev_val) / abs(prev_val) * Decimal("100")).quantize(
                    Decimal("0.1")
                )
            changes.append(
                SatelliteChangeRead(
                    index_name=name,
                    latest=latest_val,
                    previous=prev_val,
                    change_percent=pct,
                )
            )
        return changes

    def _summary(self, item: SatelliteObservation) -> SatelliteObservationSummary:
        return SatelliteObservationSummary(
            id=item.id,
            acquisition_date=item.acquisition_date,
            cloud_cover=item.cloud_cover,
            ndvi_mean=item.ndvi_mean,
            ndre_mean=item.ndre_mean,
            ndwi_mean=item.ndwi_mean,
            anomaly_count=item.anomaly_count,
            processing_status=item.processing_status.value,
            provider=item.provider,
            satellite=item.satellite,
        )

    def _observation_read(self, item: SatelliteObservation) -> SatelliteObservationRead:
        trees = self._parcel_trees(item.parcel_id)
        parcel = self.parcels.get_by_id(item.parcel_id)
        boundary = parcel.boundary if parcel is not None and isinstance(parcel.boundary, dict) else None
        zone_tree_map = {
            zone.zone_key: trees_in_zone_geometry(
                zone.geometry if isinstance(zone.geometry, dict) else None,
                trees,
                parcel_boundary=boundary,
            )
            for zone in (item.zones or [])
        }
        return SatelliteObservationRead(
            id=item.id,
            parcel_id=item.parcel_id,
            acquisition_date=item.acquisition_date,
            acquisition_at=item.acquisition_at,
            processed_at=item.processed_at,
            cloud_cover=item.cloud_cover,
            ndvi_mean=item.ndvi_mean,
            ndvi_min=item.ndvi_min,
            ndvi_max=item.ndvi_max,
            ndvi_stddev=item.ndvi_stddev,
            ndre_mean=item.ndre_mean,
            ndre_min=item.ndre_min,
            ndre_max=item.ndre_max,
            ndwi_mean=item.ndwi_mean,
            ndwi_min=item.ndwi_min,
            ndwi_max=item.ndwi_max,
            anomaly_count=item.anomaly_count,
            processing_status=item.processing_status.value,
            provider=item.provider,
            satellite=item.satellite,
            product_id=item.product_id,
            image_reference=item.image_reference,
            visualization_refs=dict(item.visualization_refs or {}),
            visualization_layers=self._visualization_layers(item),
            index_formulas=dict(item.index_formulas or INDEX_FORMULAS),
            error_message=item.error_message,
            zones=[
                SatelliteZoneRead(
                    zone_key=zone.zone_key,
                    geometry=zone.geometry,
                    ndvi=zone.ndvi,
                    ndre=zone.ndre,
                    ndwi=zone.ndwi,
                    ndvi_deviation=zone.ndvi_deviation,
                    tree_public_ids=zone_tree_map.get(zone.zone_key, []),
                )
                for zone in (item.zones or [])
            ],
            anomalies=[
                self._anomaly_read(
                    anomaly,
                    tree_public_ids=zone_tree_map.get(anomaly.zone_key or "", []),
                )
                for anomaly in (item.anomalies or [])
            ],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _parcel_trees(self, parcel_id: UUID) -> list:
        try:
            return [tree for tree, _row_number in self.trees.list_map_for_parcel(parcel_id)]
        except Exception:  # noqa: BLE001 — mapping is best-effort for display
            return []

    def _visualization_layers(self, item: SatelliteObservation) -> list[VisualizationLayerRead]:
        meta = (item.source_metadata or {}).get("visualization_layers") or {}
        refs = item.visualization_refs or {}
        if not isinstance(meta, dict):
            return []
        layers: list[VisualizationLayerRead] = []
        for index_name, layer in meta.items():
            if not isinstance(layer, dict):
                continue
            bbox = layer.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            url = refs.get(index_name) or layer.get("url")
            if not url:
                continue
            try:
                bbox_f = [float(v) for v in bbox]
            except (TypeError, ValueError):
                continue
            width = layer.get("width")
            height = layer.get("height")
            layers.append(
                VisualizationLayerRead(
                    index=str(index_name),
                    url=str(url),
                    bbox=bbox_f,
                    width=int(width) if width is not None else None,
                    height=int(height) if height is not None else None,
                    native_resolution=INDEX_NATIVE_RESOLUTION.get(str(index_name)),
                    display_resolution_m=float(
                        layer.get("display_resolution_m") or DISPLAY_RESOLUTION_M
                    ),
                )
            )
        return layers

    def sample_observation(
        self,
        owner_id: UUID,
        observation_id: UUID,
        *,
        longitude: float,
        latitude: float,
        index: str = "ndvi",
    ) -> SatelliteSampleRead:
        """Inspect a map click.

        The display PNG does not carry recoverable float values. We return the
        intersecting zone aggregate when available — never invent a pixel value.
        """
        observation = self.repo.get_for_owner(observation_id, owner_id)
        if observation is None:
            raise NotFoundError("Satelitska opservacija nije pronađena")
        index_key = index.lower().strip()
        if index_key not in {IndexName.NDVI.value, IndexName.NDRE.value, IndexName.NDWI.value}:
            index_key = IndexName.NDVI.value

        label = index_key.upper()

        for zone in observation.zones or []:
            geometry = zone.geometry if isinstance(zone.geometry, dict) else None
            if not geometry:
                continue
            if not point_in_geometry((longitude, latitude), geometry):
                continue
            raw = getattr(zone, index_key, None)
            if raw is not None:
                return SatelliteSampleRead(
                    observation_id=observation.id,
                    index=index_key,
                    acquisition_date=observation.acquisition_date,
                    longitude=longitude,
                    latitude=latitude,
                    value=raw,
                    source="zone_aggregate",
                    zone_key=zone.zone_key,
                    message=f"{label} za ovaj deo parcele (prosek male zone, ne jedno stablo).",
                )
            return SatelliteSampleRead(
                observation_id=observation.id,
                index=index_key,
                acquisition_date=observation.acquisition_date,
                longitude=longitude,
                latitude=latitude,
                value=None,
                source="unavailable",
                zone_key=zone.zone_key,
                message=(
                    f"Nema lokalnog {label} za ovu zonu. Kliknite „Osveži snimak“ da se "
                    f"NDVI/NDRE/NDWI preračunaju po zonama."
                ),
            )

        return SatelliteSampleRead(
            observation_id=observation.id,
            index=index_key,
            acquisition_date=observation.acquisition_date,
            longitude=longitude,
            latitude=latitude,
            value=None,
            source="unavailable",
            zone_key=None,
            message=f"Nema lokalnog {label} za ovu tačku (van poznate zone).",
        )

    # Bump when colormap stretch / evalscript / viz pixel size changes so cached PNGs regenerate.
    _VIZ_STRETCH_VERSION = 6

    def _zone_indices_incomplete(self, observation: SatelliteObservation) -> bool:
        """True for legacy observations that only stored NDVI per zone."""
        meta = observation.source_metadata or {}
        zone_indices = meta.get("zone_indices") if isinstance(meta, dict) else None
        if isinstance(zone_indices, list) and {"ndvi", "ndre", "ndwi"}.issubset(set(zone_indices)):
            return False
        if isinstance(zone_indices, list) and zone_indices == ["ndvi"]:
            return True
        zones = observation.zones or []
        if not zones:
            return False
        has_ndvi = any(zone.ndvi is not None for zone in zones)
        has_ndre = any(zone.ndre is not None for zone in zones)
        has_ndwi = any(zone.ndwi is not None for zone in zones)
        return bool(has_ndvi and (not has_ndre or not has_ndwi))

    def _has_index_visualization(
        self,
        observation: SatelliteObservation,
        index: str,
        *,
        geometry: dict | None = None,
    ) -> bool:
        refs = observation.visualization_refs or {}
        meta = (observation.source_metadata or {}).get("visualization_layers") or {}
        if not isinstance(refs, dict) or index not in refs:
            return False
        if not isinstance(meta, dict):
            return False
        layer = meta.get(index)
        if not isinstance(layer, dict) or not layer.get("storage_key") or not layer.get("bbox"):
            return False
        try:
            width = int(layer.get("width") or 0)
            height = int(layer.get("height") or 0)
        except (TypeError, ValueError):
            return False
        if width < 64 or height < 64:
            return False
        if int(layer.get("stretch_version") or 0) != self._VIZ_STRETCH_VERSION:
            return False
        if geometry is not None and not self._layer_bbox_matches_geometry(layer, geometry):
            return False
        return True

    def _layer_bbox_matches_geometry(self, layer: dict, geometry: dict) -> bool:
        stored = layer.get("bbox")
        if not isinstance(stored, list) or len(stored) != 4:
            return False
        try:
            from app.satellite.zones import parcel_bbox

            expected = parcel_bbox(geometry)
            # Process API pads ~0.0002°; allow slack so we don't regen on every load.
            return all(abs(float(stored[i]) - float(expected[i])) < 0.005 for i in range(4))
        except Exception:  # noqa: BLE001
            return False

    def _ensure_visualizations(
        self,
        parcel: Parcel,
        observation: SatelliteObservation,
        *,
        force: bool = False,
        indices: tuple[IndexName, ...] = (IndexName.NDVI, IndexName.NDRE, IndexName.NDWI),
    ) -> None:
        if observation.processing_status != SatelliteProcessingStatus.COMPLETED:
            return
        if not parcel.boundary:
            return
        try:
            geometry = validate_boundary_geojson(parcel.boundary)
        except Exception:  # noqa: BLE001
            return

        if not force and all(
            self._has_index_visualization(observation, item.value, geometry=geometry) for item in indices
        ):
            return

        image_id = observation.product_id or observation.image_reference
        if not image_id:
            return

        storage = get_storage()
        refs = dict(observation.visualization_refs or {})
        source_meta = dict(observation.source_metadata or {})
        layers_meta = dict(source_meta.get("visualization_layers") or {})

        for index in indices:
            if not force and self._has_index_visualization(observation, index.value, geometry=geometry):
                continue
            try:
                asset = self.provider.get_visualization(geometry, image_id, index)
            except SatelliteProviderError as exc:
                logger.warning(
                    "Visualization failed for observation %s index %s: %s",
                    observation.id,
                    index.value,
                    exc.message,
                )
                continue
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Unexpected visualization error for observation %s index %s",
                    observation.id,
                    index.value,
                )
                continue

            key = f"satellite/{parcel.id}/{observation.id}/{index.value}.png"
            storage.put(key, asset.content, asset.content_type)
            url = f"/satellite/observations/{observation.id}/visualizations/{index.value}"
            refs[index.value] = url
            bbox = list(asset.bbox) if asset.bbox else None
            if bbox is None:
                try:
                    from app.satellite.zones import parcel_bbox

                    bbox = list(parcel_bbox(geometry))
                except Exception:  # noqa: BLE001
                    bbox = None
            if bbox is None:
                continue
            layers_meta[index.value] = {
                "storage_key": key,
                "url": url,
                "bbox": bbox,
                "content_type": asset.content_type,
                "width": asset.width,
                "height": asset.height,
                "stretch_version": self._VIZ_STRETCH_VERSION,
                "display_resolution_m": float(DISPLAY_RESOLUTION_M),
                "native_resolution": INDEX_NATIVE_RESOLUTION.get(index.value),
            }

        if not layers_meta:
            return
        source_meta["visualization_layers"] = layers_meta
        observation.visualization_refs = refs
        observation.source_metadata = source_meta
        self.db.commit()

    def _anomaly_read(
        self,
        item: SatelliteAnomaly,
        *,
        tree_public_ids: list[str] | None = None,
    ) -> SatelliteAnomalyRead:
        return SatelliteAnomalyRead(
            id=item.id,
            zone_key=item.zone_key,
            tree_public_ids=list(tree_public_ids or []),
            kind=item.kind.value,
            index_name=item.index_name,
            severity=item.severity,
            message=item.message,
            details=dict(item.details or {}),
            created_at=item.created_at,
        )

    def _enqueue_intelligence(self, parcel_id, anomaly_count: int) -> None:
        try:
            from app.models.enums import ParcelAnalysisEventKind
            from app.services.intelligence import IntelligenceService

            service = IntelligenceService(self.db)
            service.enqueue_event(
                parcel_id,
                ParcelAnalysisEventKind.SATELLITE_OBSERVATION,
                {"anomaly_count": anomaly_count},
            )
            if anomaly_count > 0:
                service.enqueue_event(
                    parcel_id,
                    ParcelAnalysisEventKind.SATELLITE_ANOMALY,
                    {"anomaly_count": anomaly_count},
                )
        except Exception:  # noqa: BLE001 — never break satellite sync
            logger.exception("Failed to enqueue parcel intelligence after satellite sync")
