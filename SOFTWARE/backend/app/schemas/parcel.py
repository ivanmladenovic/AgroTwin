from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.maps import normalize_maps_url
from app.core.varieties import DEFAULT_VARIETIES, main_variety_name
from app.models.enums import WellLocation
from app.core.geojson import InvalidParcelGeometry, validate_boundary_geojson
from app.schemas.common import IDSchema
from app.services.orchard_layout import MAX_TREES

VarietyRole = Literal["main", "pollinator", "other"]


class VarietySpec(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: VarietyRole = "other"
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class RowPlanItem(BaseModel):
    row_number: int = Field(ge=1)
    variety: str = Field(min_length=1, max_length=128)
    missing_positions: list[int] = Field(default_factory=list)

    @field_validator("missing_positions")
    @classmethod
    def unique_positions(cls, value: list[int]) -> list[int]:
        return sorted(set(value))


class ParcelRead(IDSchema):
    farm_id: UUID
    name: str
    code: str
    area_hectares: Decimal | None
    latitude: Decimal | None
    longitude: Decimal | None
    altitude: Decimal | None = None
    boundary: dict | None = None
    notes: str | None
    maps_url: str | None = None
    row_count: int | None
    trees_per_row: int | None
    row_spacing_m: Decimal | None
    tree_spacing_m: Decimal | None
    default_variety: str | None
    varieties: list[VarietySpec] = Field(default_factory=list)
    default_planting_year: int | None
    starting_tree_number: int = 1
    well_location: WellLocation | None
    well_x: Decimal | None
    well_y: Decimal | None
    tree_count: int = 0


class ParcelCreate(BaseModel):
    farm_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    area_hectares: Decimal = Field(gt=0)
    row_count: int = Field(ge=1, le=200)
    trees_per_row: int = Field(ge=1, le=500)
    row_spacing_m: Decimal = Field(gt=0)
    tree_spacing_m: Decimal = Field(gt=0)
    default_variety: str | None = Field(default=None, max_length=128)
    varieties: list[VarietySpec] = Field(default_factory=list)
    row_plan: list[RowPlanItem] = Field(default_factory=list)
    planting_year: int = Field(ge=1900, le=2100)
    starting_tree_number: int = Field(default=1, ge=1)
    well_location: WellLocation | None = None
    notes: str | None = None
    maps_url: str | None = None
    altitude: Decimal | None = Field(default=None, ge=-500, le=9000)
    boundary: dict | None = None

    @field_validator("maps_url", mode="before")
    @classmethod
    def validate_maps_url(cls, value: str | None) -> str | None:
        return normalize_maps_url(value)

    @field_validator("boundary")
    @classmethod
    def validate_boundary(cls, value: dict | None) -> dict | None:
        return _validated_boundary(value)

    @model_validator(mode="after")
    def normalize_planting_plan(self) -> Self:
        varieties, default_name, plan = normalize_varieties_and_plan(
            row_count=self.row_count,
            trees_per_row=self.trees_per_row,
            varieties=list(self.varieties),
            row_plan=list(self.row_plan),
            default_variety=self.default_variety,
        )
        self.varieties = varieties
        self.default_variety = default_name
        self.row_plan = plan
        return self


def normalize_varieties_and_plan(
    *,
    row_count: int,
    trees_per_row: int,
    varieties: list[VarietySpec],
    row_plan: list[RowPlanItem],
    default_variety: str | None,
) -> tuple[list[VarietySpec], str, list[RowPlanItem]]:
    total_slots = row_count * trees_per_row
    if total_slots > MAX_TREES:
        raise ValueError(f"Voćnjak bi imao {total_slots} stabala, iznad limita od {MAX_TREES}")

    resolved = list(varieties)
    if not resolved:
        if default_variety:
            resolved = [VarietySpec(name=default_variety, role="main", color="#DC2626")]
        else:
            resolved = [VarietySpec.model_validate(item) for item in DEFAULT_VARIETIES]
    names = [item.name for item in resolved]
    if len({name.lower() for name in names}) != len(names):
        raise ValueError("Nazivi sorti moraju biti jedinstveni")
    default_name = default_variety or main_variety_name([item.model_dump() for item in resolved])
    if default_name not in names:
        default_name = names[0]

    by_row = {item.row_number: item for item in row_plan}
    if len(by_row) != len(row_plan):
        raise ValueError("Svaki red može da se pojavi samo jednom u planu sadnje")
    missing: set[tuple[int, int]] = set()
    plan: list[RowPlanItem] = []
    for row_number in range(1, row_count + 1):
        item = by_row.get(row_number)
        variety = item.variety if item else default_name
        if variety not in names:
            raise ValueError(f"Nepoznata sorta '{variety}' na redu {row_number}")
        positions = item.missing_positions if item else []
        for position in positions:
            if position < 1 or position > trees_per_row:
                raise ValueError(f"Praznina na redu {row_number} je van opsega 1…{trees_per_row}")
            missing.add((row_number, position))
        plan.append(RowPlanItem(row_number=row_number, variety=variety, missing_positions=positions))
    planted = total_slots - len(missing)
    if planted < 1:
        raise ValueError("U planu sadnje mora da ostane bar jedna sadnica")
    return resolved, default_name, plan


def _validated_boundary(value: dict | None) -> dict | None:
    if value is None:
        return None
    try:
        return validate_boundary_geojson(value)
    except InvalidParcelGeometry as exc:
        raise ValueError(str(exc)) from exc


class ParcelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    area_hectares: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None
    maps_url: str | None = None
    planting_year: int | None = Field(default=None, ge=1900, le=2100)
    varieties: list[VarietySpec] | None = None
    row_plan: list[RowPlanItem] | None = None
    altitude: Decimal | None = Field(default=None, ge=-500, le=9000)
    boundary: dict | None = None

    @field_validator("maps_url", mode="before")
    @classmethod
    def validate_maps_url(cls, value: str | None) -> str | None:
        return normalize_maps_url(value)

    @field_validator("boundary")
    @classmethod
    def validate_boundary(cls, value: dict | None) -> dict | None:
        return _validated_boundary(value)
