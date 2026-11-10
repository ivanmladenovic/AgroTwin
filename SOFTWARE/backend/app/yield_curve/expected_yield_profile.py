"""Reference expected-yield curves for planning (not guaranteed yields).

Age year rule:
  Planting calendar year = Year 1 of the curve.
  age_year = reference_year - planting_year + 1

Example: planted 2022, reference 2026 → Year 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable


class ExpectedYieldScenario(str, Enum):
    PESSIMISTIC = "pessimistic"
    REALISTIC = "realistic"
    OPTIMISTIC = "optimistic"


@dataclass(frozen=True)
class ExpectedYieldPoint:
    age_year: int
    scenario: ExpectedYieldScenario
    expected_yield_kg_per_tree: Decimal
    active: bool = True


@dataclass(frozen=True)
class ExpectedYieldProfile:
    crop: str
    version: str
    methodology_type: str
    confidence: str
    source: str
    source_note: str
    cultivar: str | None
    unit: str
    plateau_from_age: int
    points: tuple[ExpectedYieldPoint, ...]
    references: tuple[str, ...] = ()

    def points_for_scenario(self, scenario: ExpectedYieldScenario) -> list[ExpectedYieldPoint]:
        return sorted(
            [point for point in self.points if point.scenario == scenario and point.active],
            key=lambda item: item.age_year,
        )


EXPECTED_YIELD_SOURCE_NOTE = (
    "Referentna planska kriva zasnovana na javno dostupnim podacima o razvoju prinosa "
    "leske prema starosti zasada. Vrednosti krive su bruto (kg ploda u ljusci / stablo). "
    "Za poređenje sa stvarnom berbom koristi se pesimistični scenario, a neto je 40% bruto. "
    "Stvarni prinos zavisi od sorte, gustine, zemljišta, oprašivanja, navodnjavanja, "
    "ishrane, zaštite, vremenskih uslova i drugih faktora."
)

# Curve table values are GROSS (in-shell) kg/tree. Net for comparison = 40% of gross.
SHELL_TO_NET_RATIO = Decimal("0.40")


def shell_to_net(gross_kg: Decimal | None) -> Decimal | None:
    """Convert in-shell (bruto) expected yield to net kernel yield."""
    if gross_kg is None:
        return None
    return (gross_kg * SHELL_TO_NET_RATIO).quantize(Decimal("0.01"))


# kg of in-shell fruit per tree per age year (planting year = Year 1).
_HAZELNUT_SHELL_TABLE: tuple[tuple[int, str, str, str], ...] = (
    (1, "0.0", "0.0", "0.0"),
    (2, "0.0", "0.0", "0.1"),
    (3, "0.0", "0.1", "0.3"),
    (4, "0.2", "0.5", "1.0"),
    (5, "0.7", "1.5", "2.0"),
    (6, "1.2", "2.5", "3.5"),
    (7, "2.0", "3.5", "4.5"),
    (8, "2.5", "4.5", "5.5"),
    (9, "3.0", "5.0", "6.5"),
    (10, "3.5", "5.5", "7.5"),
    (11, "4.0", "6.0", "8.5"),
    (12, "4.5", "6.5", "9.5"),
    (13, "5.0", "7.0", "10.0"),
    (14, "5.0", "7.5", "11.0"),
    (15, "5.5", "8.0", "12.0"),
)


def _build_points(rows: Iterable[tuple[int, str, str, str]]) -> tuple[ExpectedYieldPoint, ...]:
    points: list[ExpectedYieldPoint] = []
    for age_year, pessimistic, realistic, optimistic in rows:
        points.extend(
            [
                ExpectedYieldPoint(
                    age_year=age_year,
                    scenario=ExpectedYieldScenario.PESSIMISTIC,
                    expected_yield_kg_per_tree=Decimal(pessimistic),
                ),
                ExpectedYieldPoint(
                    age_year=age_year,
                    scenario=ExpectedYieldScenario.REALISTIC,
                    expected_yield_kg_per_tree=Decimal(realistic),
                ),
                ExpectedYieldPoint(
                    age_year=age_year,
                    scenario=ExpectedYieldScenario.OPTIMISTIC,
                    expected_yield_kg_per_tree=Decimal(optimistic),
                ),
            ]
        )
    return tuple(points)


HAZELNUT_SHELL_YIELD_PROFILE = ExpectedYieldProfile(
    crop="hazelnut",
    cultivar=None,
    version="agrotwin-hazelnut-shell-v1",
    methodology_type="REFERENCE_CURVE",
    confidence="INFORMATIVE",
    source="AgroTwin planning benchmark",
    source_note=EXPECTED_YIELD_SOURCE_NOTE,
    unit="kg_per_tree",
    plateau_from_age=15,
    points=_build_points(_HAZELNUT_SHELL_TABLE),
    references=(
        "https://www.fao.org/4/x5337e/x5337e02.htm",
        "Public hazelnut orchard yield-by-age planning references",
    ),
)


def kg_per_tree_for_age(
    age_year: int,
    scenario: ExpectedYieldScenario,
    *,
    profile: ExpectedYieldProfile = HAZELNUT_SHELL_YIELD_PROFILE,
) -> Decimal:
    if age_year < 1:
        return Decimal("0")
    effective_age = min(age_year, profile.plateau_from_age)
    for point in profile.points_for_scenario(scenario):
        if point.age_year == effective_age:
            return point.expected_yield_kg_per_tree
    return Decimal("0")


def profile_points(
    *,
    profile: ExpectedYieldProfile = HAZELNUT_SHELL_YIELD_PROFILE,
    max_age: int | None = None,
) -> list[dict[str, Decimal | int]]:
    """Rows for the UI table/chart: age_year + three scenarios."""
    limit = max_age or profile.plateau_from_age
    rows: list[dict[str, Decimal | int]] = []
    for age in range(1, limit + 1):
        rows.append(
            {
                "age_year": age,
                "pessimistic": kg_per_tree_for_age(age, ExpectedYieldScenario.PESSIMISTIC, profile=profile),
                "realistic": kg_per_tree_for_age(age, ExpectedYieldScenario.REALISTIC, profile=profile),
                "optimistic": kg_per_tree_for_age(age, ExpectedYieldScenario.OPTIMISTIC, profile=profile),
            }
        )
    return rows
