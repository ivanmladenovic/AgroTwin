from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult
from app.context.soil_map import snapshot_is_stale, source_meta, surface_properties
from app.context.types import DataQualityStatus, SourceType, WarningType
from app.repositories.soil import SoilProfileRepository
from app.schemas.context import ContextSoilProperty, ContextSoilRead
from app.soil.properties import SOURCE_TYPE


class SoilContextProvider:
    def __init__(self, db: Session) -> None:
        self.snapshots = SoilProfileRepository(db)

    def get_source_type(self) -> str:
        return "soil"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_soil and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        snapshot = self.snapshots.get_for_parcel(parcel.id)
        meta = source_meta()
        if snapshot is None:
            warning = ContextWarning(
                WarningType.MISSING_DATA,
                "soil",
                "Nema keširanog SoilGrids profila za parcelu.",
            )
            payload = ContextSoilRead(
                status=DataQualityStatus.MISSING,
                source=meta["source"],
                source_type=SOURCE_TYPE,
                source_label=meta["source_label"],
                message=warning.message,
            )
            return ProviderResult(
                source="soil",
                source_type=SourceType.MODELED_ESTIMATE.value,
                status=DataQualityStatus.MISSING,
                payload=payload,
                warnings=[warning],
            )

        stale = snapshot_is_stale(snapshot, datetime.now(timezone.utc))
        mapped = surface_properties(snapshot.values if isinstance(snapshot.values, dict) else {})
        missing = [key for key, item in mapped.items() if not item["available"]]
        stored_missing = [item for item in snapshot.missing_properties if isinstance(item, str)]
        missing = sorted(set(missing) | set(stored_missing))
        if stale:
            status = DataQualityStatus.STALE
            message = "SoilGrids podaci su stariji od podešenog perioda svežine."
            warning_type = WarningType.STALE_DATA
        elif missing:
            status = DataQualityStatus.PARTIAL
            message = "Neki SoilGrids parametri nisu dostupni za ovu lokaciju."
            warning_type = WarningType.PARTIAL_DATA
        else:
            status = DataQualityStatus.AVAILABLE
            message = None
            warning_type = None
        surface_depth = next((item["depth_label"] for item in mapped.values() if item.get("depth_label")), None)
        payload = ContextSoilRead(
            status=status,
            source=meta["source"],
            source_type=SOURCE_TYPE,
            source_label=meta["source_label"],
            is_stale=stale,
            fetched_at=snapshot.fetched_at,
            depth=surface_depth,
            properties={key: ContextSoilProperty(**item) for key, item in mapped.items()},
            missing_properties=missing,
            message=message,
        )
        warnings = []
        if warning_type is not None and message:
            warnings.append(ContextWarning(warning_type, "soil", message))
        return ProviderResult(
            source="soil",
            source_type=SourceType.MODELED_ESTIMATE.value,
            status=status,
            payload=payload,
            collected=1,
            warnings=warnings,
        )
