from unittest import TestCase

from app.models.enums import OrganicScope, ProductionMethod, TreeStatus
from app.models.parcel import Parcel
from app.models.row import Row
from app.models.tree import Tree
from app.services.planting_resolution import (
    planting_year_distribution,
    resolve_is_organic,
    resolve_planting_year,
)


def _parcel(**kwargs) -> Parcel:
    parcel = Parcel(
        farm_id=kwargs.get("farm_id"),
        name="T",
        code="t",
        default_planting_year=kwargs.get("default_planting_year"),
        production_method=kwargs.get("production_method", ProductionMethod.CONVENTIONAL),
        organic_scope=kwargs.get("organic_scope", OrganicScope.NONE),
    )
    return parcel


def _row(parcel: Parcel, *, planting_year=None, is_organic=False) -> Row:
    return Row(
        parcel_id=parcel.id,
        row_number=1,
        tree_count=1,
        planting_year=planting_year,
        is_organic=is_organic,
    )


def _tree(row: Row, *, planting_year=None, is_organic=None) -> Tree:
    return Tree(
        parcel_id=row.parcel_id,
        row_id=row.id,
        public_id="R01-T0001",
        position_in_row=1,
        planting_year=planting_year,
        is_organic=is_organic,
        status=TreeStatus.ACTIVE,
    )


class PlantingResolutionTests(TestCase):
    def test_single_parcel_year(self) -> None:
        parcel = _parcel(default_planting_year=2022)
        self.assertEqual(resolve_planting_year(parcel=parcel), 2022)

    def test_tree_overrides_row_and_parcel(self) -> None:
        parcel = _parcel(default_planting_year=2022)
        row = _row(parcel, planting_year=2023)
        tree = _tree(row, planting_year=2024)
        self.assertEqual(resolve_planting_year(tree=tree, row=row, parcel=parcel), 2024)

    def test_row_overrides_parcel(self) -> None:
        parcel = _parcel(default_planting_year=2022)
        row = _row(parcel, planting_year=2023)
        tree = _tree(row, planting_year=None)
        self.assertEqual(resolve_planting_year(tree=tree, row=row, parcel=parcel), 2023)

    def test_distribution_multi_year(self) -> None:
        from uuid import uuid4

        parcel = _parcel(default_planting_year=2022)
        parcel.id = uuid4()
        row_a = _row(parcel, planting_year=2022)
        row_a.id = uuid4()
        row_b = _row(parcel, planting_year=2023)
        row_b.id = uuid4()
        trees = [
            _tree(row_a, planting_year=None),
            _tree(row_a, planting_year=None),
            _tree(row_b, planting_year=None),
            _tree(row_b, planting_year=2024),  # tree override
        ]
        for tree in trees:
            tree.id = uuid4()
            tree.row_id = row_a.id if tree is trees[0] or tree is trees[1] else row_b.id
        trees[0].row_id = row_a.id
        trees[1].row_id = row_a.id
        trees[2].row_id = row_b.id
        trees[3].row_id = row_b.id
        counts, unknown = planting_year_distribution(parcel=parcel, rows=[row_a, row_b], trees=trees)
        self.assertEqual(unknown, 0)
        self.assertEqual(counts[2022], 2)
        self.assertEqual(counts[2023], 1)
        self.assertEqual(counts[2024], 1)

    def test_unknown_when_no_years(self) -> None:
        from uuid import uuid4

        parcel = _parcel(default_planting_year=None)
        parcel.id = uuid4()
        row = _row(parcel, planting_year=None)
        row.id = uuid4()
        tree = _tree(row, planting_year=None)
        tree.row_id = row.id
        counts, unknown = planting_year_distribution(parcel=parcel, rows=[row], trees=[tree])
        self.assertEqual(counts, {})
        self.assertEqual(unknown, 1)

    def test_conventional_not_organic(self) -> None:
        parcel = _parcel(production_method=ProductionMethod.CONVENTIONAL)
        self.assertFalse(resolve_is_organic(parcel=parcel))

    def test_entire_parcel_organic(self) -> None:
        parcel = _parcel(
            production_method=ProductionMethod.ORGANIC,
            organic_scope=OrganicScope.ENTIRE_PARCEL,
        )
        self.assertTrue(resolve_is_organic(parcel=parcel))

    def test_part_of_parcel_row_and_tree_override(self) -> None:
        parcel = _parcel(
            production_method=ProductionMethod.ORGANIC,
            organic_scope=OrganicScope.PART_OF_PARCEL,
        )
        row = _row(parcel, is_organic=True)
        tree_inherit = _tree(row, is_organic=None)
        tree_force_off = _tree(row, is_organic=False)
        self.assertTrue(resolve_is_organic(parcel=parcel, row=row, tree=tree_inherit))
        self.assertFalse(resolve_is_organic(parcel=parcel, row=row, tree=tree_force_off))
