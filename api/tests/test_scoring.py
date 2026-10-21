import pytest

from app.models import Suburb
from app.scoring import derived_indicators, percentile_ranks, score, summarise


def make(
    code: str, *, stops: int = 10, green: float = 10, rent: int = 400, income: int = 2000, crashes: float = 20
) -> Suburb:
    return Suburb(
        code=code,
        name=code,
        state="VIC",
        latitude=-37.8,
        longitude=145.0,
        area_sqkm=2.0,
        population=10_000,
        median_age=35,
        median_weekly_rent=rent,
        median_household_income=income,
        green_space_pct=green,
        pt_stops=stops,
        road_crashes_per_year=crashes,
        reference_year=2021,
    )


def by_code(suburbs: list[Suburb]) -> dict[str, float]:
    return {s.code: s.liveability_score for s in score(suburbs)}


def test_derived_indicators():
    d = derived_indicators(make("A", stops=30, rent=500, income=2000, crashes=25))
    assert d == {
        "population_density": 5000.0,
        "pt_stops_per_sqkm": 15.0,
        "crashes_per_1000_residents": 2.5,
        "rent_to_income_pct": 25.0,
    }


def test_percentile_ranks_handle_ties():
    assert percentile_ranks([10, 20, 30]) == [0.0, 0.5, 1.0]
    assert percentile_ranks([5, 5, 9]) == [0.25, 0.25, 1.0]
    assert percentile_ranks([7]) == [0.5]


def test_best_and_worst_on_every_indicator_get_100_and_0():
    best = make("BEST", stops=100, green=40, rent=300, income=3000, crashes=5)
    worst = make("WORST", stops=1, green=1, rent=700, income=1400, crashes=90)
    assert by_code([best, worst]) == {"BEST": 100.0, "WORST": 0.0}


def test_cheaper_rent_relative_to_income_scores_higher():
    affordable = make("AFFORDABLE", rent=300)
    stretched = make("STRETCHED", rent=600)
    scores = by_code([affordable, stretched])
    # Only affordability differs, so the gap is exactly its weight (0.30) times 100.
    assert scores["AFFORDABLE"] - scores["STRETCHED"] == pytest.approx(30.0)


def test_fewer_crashes_per_resident_scores_higher():
    scores = by_code([make("SAFE", crashes=5), make("RISKY", crashes=50)])
    assert scores["SAFE"] - scores["RISKY"] == pytest.approx(15.0)


def test_outlier_does_not_flatten_everyone_else():
    # With min-max scaling the CBD-like outlier would push the others' transport score to about 0.
    areas = [make("CBD", stops=5000), make("A", stops=40), make("B", stops=20), make("C", stops=10)]
    transport = {s.code: s.liveability_score for s in score(areas)}
    assert transport["A"] > transport["B"] > transport["C"]
    assert transport["A"] - transport["C"] == pytest.approx(0.30 * 100 * 2 / 3, abs=0.1)


def test_identical_areas_score_the_midpoint():
    assert by_code([make("A"), make("B")]) == {"A": 50.0, "B": 50.0}


def test_empty_input():
    assert score([]) == []
    assert summarise([]) == []


def test_summary_statistics():
    stats = {s.indicator: s for s in summarise(score([make("A", green=10), make("B", green=30)]))}
    assert stats["green_space_pct"].min == 10
    assert stats["green_space_pct"].max == 30
    assert stats["green_space_pct"].mean == 20
    assert stats["population_density"].median == 5000
