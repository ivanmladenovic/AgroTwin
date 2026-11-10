"""Pure expected-yield calculations. No I/O."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from app.services.parcel_report_calc import percent_change, ratio
from app.yield_curve.expected_yield_profile import (
    EXPECTED_YIELD_SOURCE_NOTE,
    HAZELNUT_SHELL_YIELD_PROFILE,
    SHELL_TO_NET_RATIO,
    ExpectedYieldProfile,
    ExpectedYieldScenario,
    kg_per_tree_for_age,
    profile_points,
    shell_to_net,
)


def planting_age_year(planting_year: int, reference_year: int) -> int | None:
    """Planting calendar year = Year 1 on the reference curve."""
    if reference_year < planting_year:
        return None
    return reference_year - planting_year + 1


@dataclass(frozen=True)
class AgeCohort:
    planting_year: int
    age_year: int
    tree_count: int
    pessimistic_kg_per_tree: Decimal
    realistic_kg_per_tree: Decimal
    optimistic_kg_per_tree: Decimal

    @property
    def pessimistic_kg(self) -> Decimal:
        return self.pessimistic_kg_per_tree * self.tree_count

    @property
    def realistic_kg(self) -> Decimal:
        return self.realistic_kg_per_tree * self.tree_count

    @property
    def optimistic_kg(self) -> Decimal:
        return self.optimistic_kg_per_tree * self.tree_count


@dataclass(frozen=True)
class ExpectedYieldTotals:
    available: bool
    known_tree_count: int
    unknown_tree_count: int
    active_tree_count: int
    cohorts: tuple[AgeCohort, ...]
    # Gross = in-shell (ljuska) totals from the reference curve.
    pessimistic_kg: Decimal | None
    realistic_kg: Decimal | None
    optimistic_kg: Decimal | None
    # Net = 40% of gross, used for comparison with harvest net quantity.
    pessimistic_net_kg: Decimal | None
    realistic_net_kg: Decimal | None
    optimistic_net_kg: Decimal | None
    expected_per_tree_realistic: Decimal | None
    expected_per_hectare_realistic: Decimal | None
    expected_per_tree_realistic_net: Decimal | None
    expected_per_hectare_realistic_net: Decimal | None
    shell_to_net_ratio: Decimal = SHELL_TO_NET_RATIO
    mixed_ages: bool = False
    age_years: tuple[int, ...] = ()
    message: str | None = None
    precision_note: str | None = None
    source_note: str = EXPECTED_YIELD_SOURCE_NOTE
    profile_version: str = HAZELNUT_SHELL_YIELD_PROFILE.version
    methodology_type: str = HAZELNUT_SHELL_YIELD_PROFILE.methodology_type
    confidence: str = HAZELNUT_SHELL_YIELD_PROFILE.confidence
    source: str = HAZELNUT_SHELL_YIELD_PROFILE.source


@dataclass(frozen=True)
class ActualVsExpected:
    actual_net_kg: Decimal | None
    expected_pessimistic_net_kg: Decimal | None
    difference_kg: Decimal | None
    difference_percent: Decimal | None
    message: str | None


def build_cohorts(
    distribution: dict[int, int],
    reference_year: int,
    *,
    profile: ExpectedYieldProfile = HAZELNUT_SHELL_YIELD_PROFILE,
) -> list[AgeCohort]:
    cohorts: list[AgeCohort] = []
    for planting_year in sorted(distribution):
        count = distribution[planting_year]
        if count <= 0:
            continue
        age = planting_age_year(planting_year, reference_year)
        if age is None:
            continue
        cohorts.append(
            AgeCohort(
                planting_year=planting_year,
                age_year=age,
                tree_count=count,
                pessimistic_kg_per_tree=kg_per_tree_for_age(
                    age, ExpectedYieldScenario.PESSIMISTIC, profile=profile
                ),
                realistic_kg_per_tree=kg_per_tree_for_age(
                    age, ExpectedYieldScenario.REALISTIC, profile=profile
                ),
                optimistic_kg_per_tree=kg_per_tree_for_age(
                    age, ExpectedYieldScenario.OPTIMISTIC, profile=profile
                ),
            )
        )
    return cohorts


def compute_expected_yield(
    *,
    distribution: dict[int, int],
    unknown_tree_count: int,
    reference_year: int,
    area_hectares: Decimal | None = None,
    profile: ExpectedYieldProfile = HAZELNUT_SHELL_YIELD_PROFILE,
) -> ExpectedYieldTotals:
    cohorts = build_cohorts(distribution, reference_year, profile=profile)
    known = sum(item.tree_count for item in cohorts)
    active = known + max(0, unknown_tree_count)
    if known <= 0:
        message = "Nema dovoljno podataka o starosti zasada za izračunavanje očekivanog prinosa."
        precision = None
        if active > 0 and unknown_tree_count > 0:
            precision = f"Procena nije moguća: nedostaje godina sadnje za {unknown_tree_count} od {active} stabala."
        return ExpectedYieldTotals(
            available=False,
            known_tree_count=0,
            unknown_tree_count=unknown_tree_count,
            active_tree_count=active,
            cohorts=tuple(),
            pessimistic_kg=None,
            realistic_kg=None,
            optimistic_kg=None,
            pessimistic_net_kg=None,
            realistic_net_kg=None,
            optimistic_net_kg=None,
            expected_per_tree_realistic=None,
            expected_per_hectare_realistic=None,
            expected_per_tree_realistic_net=None,
            expected_per_hectare_realistic_net=None,
            mixed_ages=False,
            age_years=tuple(),
            message=message,
            precision_note=precision,
            profile_version=profile.version,
            methodology_type=profile.methodology_type,
            confidence=profile.confidence,
            source=profile.source,
            source_note=profile.source_note,
        )

    pessimistic = sum((item.pessimistic_kg for item in cohorts), Decimal("0"))
    realistic = sum((item.realistic_kg for item in cohorts), Decimal("0"))
    optimistic = sum((item.optimistic_kg for item in cohorts), Decimal("0"))
    realistic_net = shell_to_net(realistic)
    per_tree = ratio(realistic, Decimal(known))
    per_ha = ratio(realistic, area_hectares) if area_hectares is not None else None
    ages = tuple(sorted({item.age_year for item in cohorts}))
    precision = None
    if unknown_tree_count > 0:
        precision = f"Procena je zasnovana na {known} od {active} stabala."
    return ExpectedYieldTotals(
        available=True,
        known_tree_count=known,
        unknown_tree_count=unknown_tree_count,
        active_tree_count=active,
        cohorts=tuple(cohorts),
        pessimistic_kg=pessimistic,
        realistic_kg=realistic,
        optimistic_kg=optimistic,
        pessimistic_net_kg=shell_to_net(pessimistic),
        realistic_net_kg=realistic_net,
        optimistic_net_kg=shell_to_net(optimistic),
        expected_per_tree_realistic=per_tree,
        expected_per_hectare_realistic=per_ha,
        expected_per_tree_realistic_net=shell_to_net(per_tree) if per_tree is not None else None,
        expected_per_hectare_realistic_net=shell_to_net(per_ha) if per_ha is not None else None,
        mixed_ages=len(ages) > 1,
        age_years=ages,
        message=None,
        precision_note=precision,
        profile_version=profile.version,
        methodology_type=profile.methodology_type,
        confidence=profile.confidence,
        source=profile.source,
        source_note=profile.source_note,
    )


def compare_actual_to_expected(
    actual_net_kg: Decimal | None,
    expected_pessimistic_gross_kg: Decimal | None,
) -> ActualVsExpected:
    """Compare harvest NET to pessimistic expected NET (40% of in-shell gross)."""
    expected_net = shell_to_net(expected_pessimistic_gross_kg)
    if actual_net_kg is None or expected_net is None:
        return ActualVsExpected(
            actual_net_kg=actual_net_kg,
            expected_pessimistic_net_kg=expected_net,
            difference_kg=None,
            difference_percent=None,
            message=None,
        )
    difference_kg = actual_net_kg - expected_net
    difference_percent = None
    if expected_net != 0:
        difference_percent = percent_change(actual_net_kg, expected_net)
    message = _comparison_message(difference_kg, difference_percent, expected_net)
    return ActualVsExpected(
        actual_net_kg=actual_net_kg,
        expected_pessimistic_net_kg=expected_net,
        difference_kg=difference_kg,
        difference_percent=difference_percent,
        message=message,
    )


def _comparison_message(
    difference_kg: Decimal,
    difference_percent: Decimal | None,
    expected_pessimistic_net_kg: Decimal,
) -> str:
    if expected_pessimistic_net_kg == 0:
        if difference_kg == 0:
            return "Stvarni neto prinos je u skladu sa pesimističnim scenarijem (očekivano 0 kg neto)."
        return "Stvarni neto prinos odstupa od pesimističnog scenarija (očekivano 0 kg neto)."
    if difference_percent is None:
        return "Stvarni neto prinos odstupa od pesimističnog scenarija."
    abs_pct = abs(difference_percent).quantize(Decimal("0.1"))
    if difference_kg == 0:
        return "Stvarni neto prinos je u skladu sa pesimističnim scenarijem."
    if difference_kg > 0:
        return f"Stvarni neto prinos je {abs_pct}% iznad pesimističnog scenarija."
    return f"Stvarni neto prinos je {abs_pct}% ispod pesimističnog scenarija."


def curve_table(
    *,
    profile: ExpectedYieldProfile = HAZELNUT_SHELL_YIELD_PROFILE,
    highlight_ages: Iterable[int] | None = None,
) -> list[dict]:
    highlighted = set(highlight_ages or [])
    rows = []
    for row in profile_points(profile=profile):
        age = int(row["age_year"])
        rows.append(
            {
                **row,
                "is_current": age in highlighted,
            }
        )
    return rows
