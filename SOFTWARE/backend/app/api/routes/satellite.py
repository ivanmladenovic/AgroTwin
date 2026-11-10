from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import CurrentUser, DBSession
from app.schemas.satellite import (
    ParcelSatelliteMonitoringRead,
    SatelliteHistoryRead,
    SatelliteObservationRead,
    SatelliteObservationSummary,
    SatelliteSampleRead,
    SatelliteSyncResultRead,
)
from app.services.satellite import SatelliteService

router = APIRouter(tags=["satellite"])


@router.get(
    "/parcels/{parcel_id}/satellite",
    response_model=ParcelSatelliteMonitoringRead,
)
def get_parcel_satellite_monitoring(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ParcelSatelliteMonitoringRead:
    """Read cached satellite monitoring. Does not trigger provider downloads."""
    return SatelliteService(db).get_monitoring(current_user.id, parcel_id)


@router.get(
    "/parcels/{parcel_id}/satellite/history",
    response_model=SatelliteHistoryRead,
)
def get_parcel_satellite_history(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> SatelliteHistoryRead:
    """Stored index history for one parcel. Does not download a new scene."""
    return SatelliteService(db).get_history(
        current_user.id,
        parcel_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/parcels/{parcel_id}/satellite/observations",
    response_model=list[SatelliteObservationSummary],
)
def list_parcel_satellite_observations(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[SatelliteObservationSummary]:
    return SatelliteService(db).list_observations(current_user.id, parcel_id)


@router.get(
    "/satellite/observations/{observation_id}",
    response_model=SatelliteObservationRead,
)
def get_satellite_observation(
    observation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> SatelliteObservationRead:
    return SatelliteService(db).get_observation(current_user.id, observation_id)


@router.get("/satellite/observations/{observation_id}/visualizations/{index_name}")
def get_satellite_visualization(
    observation_id: UUID,
    index_name: str,
    current_user: CurrentUser,
    db: DBSession,
) -> Response:
    content, content_type = SatelliteService(db).get_visualization_bytes(
        current_user.id,
        observation_id,
        index_name.lower().strip(),
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get(
    "/satellite/observations/{observation_id}/sample",
    response_model=SatelliteSampleRead,
)
def sample_satellite_observation(
    observation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    longitude: float = Query(..., ge=-180, le=180),
    latitude: float = Query(..., ge=-90, le=90),
    index: str = Query("ndvi"),
) -> SatelliteSampleRead:
    """Map click inspect — zone aggregate only; never invents PNG pixel floats."""
    return SatelliteService(db).sample_observation(
        current_user.id,
        observation_id,
        longitude=longitude,
        latitude=latitude,
        index=index,
    )


@router.post(
    "/parcels/{parcel_id}/satellite/refresh",
    response_model=SatelliteSyncResultRead,
)
def refresh_parcel_satellite(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> SatelliteSyncResultRead:
    """Manually request processing of the newest valid Sentinel-2 scene."""
    return SatelliteService(db).refresh_parcel(current_user.id, parcel_id)
