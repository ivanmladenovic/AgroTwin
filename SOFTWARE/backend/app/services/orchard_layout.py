from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import WellLocation

MAX_TREES = 20_000


@dataclass(frozen=True)
class LayoutTree:
    row_number: int
    position_in_row: int
    public_id: str
    sequence_number: int
    normalized_x: Decimal
    normalized_y: Decimal
    planting_year: int | None
    variety: str | None


@dataclass(frozen=True)
class LayoutRow:
    row_number: int
    tree_count: int
    variety: str | None
    trees: tuple[LayoutTree, ...]


@dataclass(frozen=True)
class OrchardLayout:
    rows: tuple[LayoutRow, ...]
    tree_count: int
    width_m: Decimal
    height_m: Decimal
    well_x: Decimal | None
    well_y: Decimal | None


def format_tree_public_id(row_number: int, sequence_number: int) -> str:
    return f"R{row_number:02d}-T{sequence_number:04d}"


def well_coordinates(
    location: WellLocation | None,
    width_m: Decimal,
    height_m: Decimal,
    row_spacing_m: Decimal,
    tree_spacing_m: Decimal,
) -> tuple[Decimal | None, Decimal | None]:
    if location is None:
        return None, None
    offset_x = tree_spacing_m * Decimal("0.65")
    offset_y = row_spacing_m * Decimal("0.65")
    mid_x = width_m / 2
    mid_y = height_m / 2
    mapping: dict[WellLocation, tuple[Decimal, Decimal]] = {
        WellLocation.NORTHWEST: (-offset_x, Decimal("0")),
        WellLocation.NORTH: (mid_x, -offset_y),
        WellLocation.NORTHEAST: (width_m + offset_x, Decimal("0")),
        WellLocation.WEST: (-offset_x, mid_y),
        WellLocation.EAST: (width_m + offset_x, mid_y),
        WellLocation.SOUTHWEST: (-offset_x, height_m),
        WellLocation.SOUTH: (mid_x, height_m + offset_y),
        WellLocation.SOUTHEAST: (width_m + offset_x, height_m),
    }
    return mapping[location]


def generate_rectangular_layout(
    *,
    row_count: int,
    trees_per_row: int,
    row_spacing_m: Decimal,
    tree_spacing_m: Decimal,
    starting_tree_number: int = 1,
    default_variety: str | None = None,
    planting_year: int | None = None,
    well_location: WellLocation | None = None,
    row_varieties: dict[int, str] | None = None,
    missing_positions: set[tuple[int, int]] | None = None,
) -> OrchardLayout:
    if row_count < 1 or trees_per_row < 1:
        raise ValueError("Broj redova i broj sadnica u redu moraju biti najmanje 1")
    total_slots = row_count * trees_per_row
    if total_slots > MAX_TREES:
        raise ValueError(f"Voćnjak bi imao {total_slots} stabala, iznad limita od {MAX_TREES}")
    if row_spacing_m <= 0 or tree_spacing_m <= 0:
        raise ValueError("Razmak mora biti veći od nule")
    if starting_tree_number < 1:
        raise ValueError("Početni broj stabla mora biti najmanje 1")

    skipped = missing_positions or set()
    varieties = row_varieties or {}
    width_m = Decimal(max(trees_per_row - 1, 0)) * tree_spacing_m
    height_m = Decimal(max(row_count - 1, 0)) * row_spacing_m
    rows: list[LayoutRow] = []
    sequence = starting_tree_number
    planted = 0

    for row_number in range(1, row_count + 1):
        generated: list[LayoutTree] = []
        y = Decimal(row_number - 1) * row_spacing_m
        variety = varieties.get(row_number, default_variety)
        for position in range(1, trees_per_row + 1):
            public_id = format_tree_public_id(row_number, sequence)
            sequence += 1
            if (row_number, position) in skipped:
                continue
            x = Decimal(position - 1) * tree_spacing_m
            generated.append(
                LayoutTree(
                    row_number=row_number,
                    position_in_row=position,
                    public_id=public_id,
                    sequence_number=sequence - 1,
                    normalized_x=x,
                    normalized_y=y,
                    planting_year=planting_year,
                    variety=variety,
                )
            )
            planted += 1
        rows.append(
            LayoutRow(
                row_number=row_number,
                tree_count=len(generated),
                variety=variety,
                trees=tuple(generated),
            )
        )

    if planted < 1:
        raise ValueError("U planu sadnje mora da ostane bar jedna sadnica")

    well_x, well_y = well_coordinates(well_location, width_m, height_m, row_spacing_m, tree_spacing_m)
    return OrchardLayout(
        rows=tuple(rows),
        tree_count=planted,
        width_m=width_m,
        height_m=height_m,
        well_x=well_x,
        well_y=well_y,
    )
