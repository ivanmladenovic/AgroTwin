"""Resolve effective planting year and organic status for planning.

Hierarchy (planting year):
  TREE.planting_year
  → ROW.planting_year
  → PARCEL.default_planting_year
  → unknown (None)

Hierarchy (organic):
  if production_method != organic → False
  if organic_scope == entire_parcel → True
  if organic_scope == part_of_parcel:
      TREE.is_organic if not None
      → ROW.is_organic
      → False
  else → False
"""

from __future__ import annotations

from app.models.enums import OrganicScope, ProductionMethod, TreeStatus
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree


def resolve_planting_year(
    *,
    tree: Tree | None = None,
    row: Row | None = None,
    parcel: Parcel | None = None,
    tree_planting_year: int | None = None,
    row_planting_year: int | None = None,
    parcel_planting_year: int | None = None,
) -> int | None:
    if tree is not None and tree.planting_year is not None:
        return tree.planting_year
    if tree_planting_year is not None:
        return tree_planting_year
    if row is not None and row.planting_year is not None:
        return row.planting_year
    if row_planting_year is not None:
        return row_planting_year
    if parcel is not None and parcel.default_planting_year is not None:
        return parcel.default_planting_year
    return parcel_planting_year


def resolve_is_organic(
    *,
    parcel: Parcel,
    row: Row | None = None,
    tree: Tree | None = None,
) -> bool:
    if parcel.production_method != ProductionMethod.ORGANIC:
        return False
    if parcel.organic_scope == OrganicScope.ENTIRE_PARCEL:
        return True
    if parcel.organic_scope != OrganicScope.PART_OF_PARCEL:
        return False
    if tree is not None and tree.is_organic is not None:
        return bool(tree.is_organic)
    if row is not None:
        return bool(row.is_organic)
    return False


def planting_year_distribution(
    *,
    parcel: Parcel,
    rows: list[Row],
    trees: list[Tree],
) -> tuple[dict[int, int], int]:
    """Return (year → active tree count, unknown_count)."""
    rows_by_id = {row.id: row for row in rows}
    counts: dict[int, int] = {}
    unknown = 0
    for tree in trees:
        if tree.status != TreeStatus.ACTIVE:
            continue
        row = rows_by_id.get(tree.row_id)
        year = resolve_planting_year(tree=tree, row=row, parcel=parcel)
        if year is None:
            unknown += 1
        else:
            counts[year] = counts.get(year, 0) + 1
    return counts, unknown


def planting_age_year(planting_year: int, reference_year: int) -> int | None:
    """Planting calendar year = Year 1 on the expected-yield curve."""
    if reference_year < planting_year:
        return None
    return reference_year - planting_year + 1
