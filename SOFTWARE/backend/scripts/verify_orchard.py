from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from decimal import Decimal

from app.services.orchard_layout import format_tree_public_id, generate_rectangular_layout


def verify_layout_26x73() -> None:
    layout = generate_rectangular_layout(
        row_count=26,
        trees_per_row=73,
        row_spacing_m=Decimal("5.00"),
        tree_spacing_m=Decimal("3.50"),
        starting_tree_number=1,
        default_variety="Tonda di Giffoni",
        planting_year=2022,
    )
    assert layout.tree_count == 1898, layout.tree_count
    assert len(layout.rows) == 26, len(layout.rows)
    assert all(row.tree_count == 73 for row in layout.rows)
    first = layout.rows[0].trees[0]
    last = layout.rows[-1].trees[-1]
    assert first.public_id == "R01-T0001", first.public_id
    assert last.public_id == format_tree_public_id(26, 1898), last.public_id
    assert last.public_id == "R26-T1898", last.public_id
    row_14 = layout.rows[13]
    assert row_14.row_number == 14
    assert row_14.trees[0].public_id == "R14-T0950"
    assert row_14.trees[-1].public_id == "R14-T1022"
    assert first.normalized_x == Decimal("0")
    assert first.normalized_y == Decimal("0")
    assert last.normalized_x == Decimal("72") * Decimal("3.50")
    assert last.normalized_y == Decimal("25") * Decimal("5.00")
    print("26 × 73 layout verified: 26 rows, 1,898 trees, IDs R01-T0001 … R26-T1898")


def verify_varieties_and_gaps() -> None:
    layout = generate_rectangular_layout(
        row_count=4,
        trees_per_row=6,
        row_spacing_m=Decimal("5.00"),
        tree_spacing_m=Decimal("3.50"),
        default_variety="Tonda di Giffoni",
        row_varieties={
            1: "Tonda di Giffoni",
            2: "Tonda Gentile Romana",
            3: "Nocchione",
            4: "Tonda di Giffoni",
        },
        missing_positions={(1, 3), (2, 1), (2, 6)},
    )
    assert layout.tree_count == 21, layout.tree_count
    assert layout.rows[0].variety == "Tonda di Giffoni"
    assert layout.rows[1].variety == "Tonda Gentile Romana"
    assert layout.rows[2].variety == "Nocchione"
    assert layout.rows[0].tree_count == 5
    assert [tree.position_in_row for tree in layout.rows[0].trees] == [1, 2, 4, 5, 6]
    assert layout.rows[1].trees[0].position_in_row == 2
    assert layout.rows[0].trees[2].normalized_x == Decimal("3") * Decimal("3.50")
    print("Variety rows and seedling gaps verified.")


if __name__ == "__main__":
    verify_layout_26x73()
    verify_varieties_and_gaps()
