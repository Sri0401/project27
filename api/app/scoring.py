"""Liveability scoring and indicator statistics.

Each indicator is min-max normalised across all suburbs to the range 0..1. The score is then
a weighted sum scaled to 0..100. Rent is inverted so that cheaper suburbs score higher.
"""

from collections.abc import Sequence
from statistics import fmean, median

from .models import IndicatorSummary, Suburb

WEIGHTS: dict[str, float] = {
    "walk_score": 0.35,
    "green_space_pct": 0.25,
    "pt_stops": 0.25,
    "median_weekly_rent": 0.15,
}
LOWER_IS_BETTER = {"median_weekly_rent"}

SUMMARY_INDICATORS = (
    "population",
    "median_age",
    "median_weekly_rent",
    "walk_score",
    "green_space_pct",
    "pt_stops",
)


def liveability_scores(suburbs: Sequence[Suburb]) -> dict[str, float]:
    """Return {suburb code: score}. Scores are relative to the suburbs passed in."""
    if not suburbs:
        return {}

    normalised: dict[str, dict[str, float]] = {s.code: {} for s in suburbs}
    for indicator in WEIGHTS:
        values = [float(getattr(s, indicator)) for s in suburbs]
        low, high = min(values), max(values)
        span = high - low
        for s, value in zip(suburbs, values, strict=True):
            # If every suburb has the same value, the indicator cannot rank them, so use the midpoint.
            norm = 0.5 if span == 0 else (value - low) / span
            if indicator in LOWER_IS_BETTER:
                norm = 1 - norm
            normalised[s.code][indicator] = norm

    return {
        code: round(100 * sum(WEIGHTS[i] * v for i, v in parts.items()), 1)
        for code, parts in normalised.items()
    }


def summarise(suburbs: Sequence[Suburb]) -> list[IndicatorSummary]:
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
