"""Derived indicators, liveability scoring and summary statistics.

The score is a weighted average of percentile ranks. For each indicator, an area's rank is the share
of other areas it beats. Percentile ranks are robust to outliers: with min-max scaling, a single
extreme value (the CBD's stop density, for example) would squash every other area towards zero.
"""

from collections.abc import Sequence
from statistics import fmean, median

from .models import IndicatorSummary, ScoredSuburb, Suburb

WEIGHTS: dict[str, float] = {
    "pt_stops_per_sqkm": 0.30,  # access to public transport
    "green_space_pct": 0.25,  # access to parks
    "rent_to_income_pct": 0.30,  # housing affordability
    "crashes_per_1000_residents": 0.15,  # road safety
}
LOWER_IS_BETTER = {"rent_to_income_pct", "crashes_per_1000_residents"}

SUMMARY_INDICATORS = (
    "population",
    "population_density",
    "median_age",
    "median_weekly_rent",
    "median_household_income",
    "rent_to_income_pct",
    "green_space_pct",
    "pt_stops_per_sqkm",
    "crashes_per_1000_residents",
)


def derived_indicators(s: Suburb) -> dict[str, float]:
    return {
        "population_density": round(s.population / s.area_sqkm, 1),
        "pt_stops_per_sqkm": round(s.pt_stops / s.area_sqkm, 2),
        "crashes_per_1000_residents": round(1000 * s.road_crashes_per_year / s.population, 2)
        if s.population
        else 0.0,
        "rent_to_income_pct": round(100 * s.median_weekly_rent / s.median_household_income, 1)
        if s.median_household_income
        else 0.0,
    }


def percentile_ranks(values: Sequence[float]) -> list[float]:
    """Rank each value from 0 (lowest) to 1 (highest). Tied values share the average rank."""
    n = len(values)
    if n == 1:
        return [0.5]
    ranks = []
    for v in values:
        below = sum(1 for other in values if other < v)
        equal = sum(1 for other in values if other == v) - 1  # exclude itself
        ranks.append((below + equal / 2) / (n - 1))
    return ranks


def score(suburbs: Sequence[Suburb]) -> list[ScoredSuburb]:
    """Add derived indicators and a liveability score that is relative to the suburbs passed in."""
    if not suburbs:
        return []
    derived = [derived_indicators(s) for s in suburbs]
    rows = [s.model_dump() | d for s, d in zip(suburbs, derived, strict=True)]

    totals = [0.0] * len(suburbs)
    for indicator, weight in WEIGHTS.items():
        for i, rank in enumerate(percentile_ranks([float(r[indicator]) for r in rows])):
            totals[i] += weight * (1 - rank if indicator in LOWER_IS_BETTER else rank)

    return [
        ScoredSuburb(**s.model_dump(), **d, liveability_score=round(100 * total, 1))
        for s, d, total in zip(suburbs, derived, totals, strict=True)
    ]


def summarise(suburbs: Sequence[ScoredSuburb]) -> list[IndicatorSummary]:
    if not suburbs:
        return []
    summaries = []
    for indicator in SUMMARY_INDICATORS:
        values = [float(getattr(s, indicator)) for s in suburbs]
        summaries.append(
            IndicatorSummary(
                indicator=indicator,
                min=min(values),
                max=max(values),
                mean=round(fmean(values), 2),
                median=round(median(values), 2),
            )
        )
    return summaries
