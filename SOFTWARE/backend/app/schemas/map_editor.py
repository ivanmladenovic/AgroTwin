"""Schemas for the isolated geographic parcel map editor."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MapEditorPlantingConfig(BaseModel):
    orientation_deg: float = Field(ge=0, lt=180)
    """When set, orientation is taken from this polygon outer-ring edge (metric CRS)."""
    orientation_edge_index: int | None = Field(default=None, ge=0, le=10_000)
    row_spacing_m: float = Field(gt=0, le=50)
    tree_spacing_m: float = Field(gt=0, le=50)
    first_row_offset_m: float = Field(default=0, ge=0, le=50)
    last_row_offset_m: float = Field(default=0, ge=0, le=50)
    row_end_offset_m: float = Field(default=0, ge=0, le=50)
    tree_start_offset_m: float | None = Field(default=None, ge=0, le=50)
    boundary_buffer_m: float = Field(default=0, ge=0, le=20)
    target_row_count: int | None = Field(default=None, ge=1, le=10_000)
    start_row_number: int = Field(default=1, ge=1, le=10_000)
    number_rows_ascending: bool = True
    default_variety: str | None = Field(default=None, max_length=128)
    default_planting_year: int | None = Field(default=None, ge=1900, le=2100)


class MapEditorResolveLocationRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2048)


class MapEditorResolveLocationRead(BaseModel):
    latitude: float
    longitude: float
    label: str
    source: Literal["coordinates", "maps_url", "geocode"]


class MapEditorMetricsRead(BaseModel):
    area_m2: float
    area_ha: float
    perimeter_m: float
    vertex_count: int
    edge_lengths_m: list[float] = Field(default_factory=list)
    self_intersecting: bool = False
    origin_lon: float | None = None
    origin_lat: float | None = None


class MapEditorPreviewRequest(BaseModel):
    boundary: dict[str, Any]
    config: MapEditorPlantingConfig


class MapEditorRowDraft(BaseModel):
    draft_id: str
    row_number: int
    segment_index: int = 0
    length_m: float
    tree_count: int
    geometry: dict[str, Any]
    default_variety: str | None = None
    default_planting_year: int | None = None


class MapEditorTreeDraft(BaseModel):
    draft_id: str
    row_draft_id: str
    row_number: int
    tree_number: int
    latitude: float
    longitude: float
    variety: str | None = None
    planting_year: int | None = None
    inherited_variety: bool = True
    manually_placed: bool = False
    existing_tree_id: UUID | None = None
    existing_public_id: str | None = None


class MapEditorPreviewRead(BaseModel):
    boundary: dict[str, Any]
    metrics: MapEditorMetricsRead
    suggested_orientation_deg: float
    config: dict[str, Any]
    rows: list[MapEditorRowDraft]
    trees: list[MapEditorTreeDraft]
    summary: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MapEditorMetricsRequest(BaseModel):
    boundary: dict[str, Any]


class MapEditorExistingTreeRead(BaseModel):
    id: UUID
    public_id: str
    row_id: UUID
    row_number: int
    position_in_row: int
    latitude: float | None
    longitude: float | None
    variety: str | None
    planting_year: int | None
    status: str
    has_geographic_position: bool


class MapEditorExistingRowRead(BaseModel):
    id: UUID
    row_number: int
    tree_count: int
    variety: str | None
    planting_year: int | None
    geometry: dict[str, Any] | None = None
    segment_count: int = 1


class MapEditorStateRead(BaseModel):
    parcel_id: UUID
    name: str
    farm_id: UUID
    boundary: dict[str, Any] | None
    latitude: Decimal | None
    longitude: Decimal | None
    area_hectares: Decimal | None
    row_spacing_m: Decimal | None
    tree_spacing_m: Decimal | None
    default_variety: str | None
    varieties: list[dict[str, Any]] = Field(default_factory=list)
    default_planting_year: int | None
    map_layout: dict[str, Any] | None = None
    metrics: MapEditorMetricsRead | None = None
    has_geographic_boundary: bool
    has_schematic_only_layout: bool
    rows: list[MapEditorExistingRowRead]
    trees: list[MapEditorExistingTreeRead]
    suggested_orientation_deg: float | None = None
    warnings: list[str] = Field(default_factory=list)


class MapEditorVarietyIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: Literal["main", "pollinator", "other"] = "other"
    color: str = Field(default="#DC2626", max_length=32)


class MapEditorCommitRequest(BaseModel):
    boundary: dict[str, Any]
    config: MapEditorPlantingConfig
    """When true, regenerate/replace tree geographic positions from preview layout.
    Existing tree records are matched by (row_number, position_in_row) when possible;
    unmatched new positions create trees only if create_missing_trees is true.
    Unmatched existing trees are left intact unless remove_unmatched_trees is true.
    """
    replace_planting: bool = False
    create_missing_trees: bool = False
    remove_unmatched_trees: bool = False
    update_area_from_geometry: bool = True
    rows: list[MapEditorRowDraft] | None = None
    trees: list[MapEditorTreeDraft] | None = None
    varieties: list[MapEditorVarietyIn] | None = None


class MapEditorCommitResult(BaseModel):
    parcel_id: UUID
    boundary: dict[str, Any]
    metrics: MapEditorMetricsRead
    map_layout: dict[str, Any]
    rows_updated: int
    trees_updated: int
    trees_created: int
    trees_removed: int
    warnings: list[str] = Field(default_factory=list)
    committed_at: datetime


class MapEditorDraftCreate(BaseModel):
    """Create a draft parcel shell for Workflow B (geographic-first)."""

    farm_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    boundary: dict[str, Any]
    config: MapEditorPlantingConfig | None = None
    commit_planting: bool = False


EditorMode = Literal[
    "select",
    "draw_boundary",
    "edit_boundary",
    "row_orientation",
    "generate_layout",
    "select_row",
    "select_tree",
    "edit_tree",
    "measure",
    "inspect_index",
]
