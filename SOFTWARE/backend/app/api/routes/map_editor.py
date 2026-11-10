"""Isolated map editor API — does not replace existing parcel/orchard canvas endpoints."""

import re
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import AppError
from app.core.maps import geocode_place, parse_google_maps_url, resolve_maps_location
from app.schemas.map_editor import (
    MapEditorCommitRequest,
    MapEditorCommitResult,
    MapEditorDraftCreate,
    MapEditorMetricsRead,
    MapEditorMetricsRequest,
    MapEditorPreviewRead,
    MapEditorPreviewRequest,
    MapEditorResolveLocationRead,
    MapEditorResolveLocationRequest,
    MapEditorStateRead,
)
from app.services.map_editor import MapEditorService

router = APIRouter(tags=["map-editor"])


@router.post("/map-editor/resolve-location", response_model=MapEditorResolveLocationRead)
def resolve_map_editor_location(
    payload: MapEditorResolveLocationRequest,
    current_user: CurrentUser,
) -> MapEditorResolveLocationRead:
    """Resolve address, lat/lng, or Google Maps URL to a map center (wizard step 2)."""
    _ = current_user
    raw = payload.query.strip()
    if not raw:
        raise AppError("Unesite adresu, koordinate ili Google Maps link.", code="location_empty", status_code=400)

    plain = re.match(r"^(-?\d+(?:\.\d+)?)\s*,\s*\+?(-?\d+(?:\.\d+)?)$", raw)
    if plain:
        loc = parse_google_maps_url(raw)
        if loc:
            return MapEditorResolveLocationRead(
                latitude=loc.lat,
                longitude=loc.lng,
                label=f"{loc.lat:.6f}, {loc.lng:.6f}",
                source="coordinates",
            )

    maps = resolve_maps_location(raw)
    if maps and ("maps." in raw.lower() or "goo.gl" in raw.lower() or "google." in raw.lower()):
        return MapEditorResolveLocationRead(
            latitude=maps.lat,
            longitude=maps.lng,
            label=raw[:120],
            source="maps_url",
        )
    if maps and parse_google_maps_url(raw):
        return MapEditorResolveLocationRead(
            latitude=maps.lat,
            longitude=maps.lng,
            label=f"{maps.lat:.6f}, {maps.lng:.6f}",
            source="coordinates",
        )

    geocoded = geocode_place(raw) or maps
    if not geocoded:
        raise AppError(
            "Lokacija nije pronađena. Probajte drugu adresu, koordinate (44.29, 21.16) ili Maps link.",
            code="location_not_found",
            status_code=404,
        )
    return MapEditorResolveLocationRead(
        latitude=geocoded.lat,
        longitude=geocoded.lng,
        label=raw[:120],
        source="geocode",
    )


@router.get("/parcels/{parcel_id}/map-editor", response_model=MapEditorStateRead)
def get_map_editor_state(
    parcel_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorStateRead:
    return MapEditorService(db).get_state(current_user.id, parcel_id)


@router.post("/parcels/{parcel_id}/map-editor/metrics", response_model=MapEditorMetricsRead)
def compute_map_editor_metrics(
    parcel_id: UUID,
    payload: MapEditorMetricsRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorMetricsRead:
    return MapEditorService(db).compute_metrics(current_user.id, parcel_id, payload.boundary)


@router.post("/map-editor/metrics", response_model=MapEditorMetricsRead)
def compute_map_editor_metrics_anonymous_parcel(
    payload: MapEditorMetricsRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorMetricsRead:
    """Metrics for Workflow B before a parcel id exists."""
    return MapEditorService(db).compute_metrics(current_user.id, None, payload.boundary)


@router.post("/parcels/{parcel_id}/map-editor/preview", response_model=MapEditorPreviewRead)
def preview_map_editor_layout(
    parcel_id: UUID,
    payload: MapEditorPreviewRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorPreviewRead:
    return MapEditorService(db).preview(current_user.id, parcel_id, payload)


@router.post("/map-editor/preview", response_model=MapEditorPreviewRead)
def preview_map_editor_layout_new(
    payload: MapEditorPreviewRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorPreviewRead:
    return MapEditorService(db).preview(current_user.id, None, payload)


@router.post("/parcels/{parcel_id}/map-editor/commit", response_model=MapEditorCommitResult)
def commit_map_editor(
    parcel_id: UUID,
    payload: MapEditorCommitRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorCommitResult:
    return MapEditorService(db).commit(current_user.id, parcel_id, payload)


@router.post("/map-editor/parcels", response_model=MapEditorStateRead)
def create_map_editor_parcel(
    payload: MapEditorDraftCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> MapEditorStateRead:
    """Workflow B: create parcel from drawn boundary (does not use rectangular CreateParcel flow)."""
    return MapEditorService(db).create_draft_parcel(current_user.id, payload)
