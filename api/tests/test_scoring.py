import pytest

from app.models import Suburb
from app.scoring import liveability_scores, summarise


def make(code: str, walk: int, green: float, stops: int, rent: int) -> Suburb:
    return Suburb(
        code=code,
        name=code,
        state="VIC",
        latitude=-37.8,
        longitude=145.0,
        population=1000,
        median_age=35,
        median_weekly_rent=rent,
        walk_score=walk,
        green_space_pct=green,
        pt_stops=stops,
        reference_year=2026,
    )


def test_best_and_worst_get_100_and_0():
    best = make("BEST", walk=100, green=30, stops=100, rent=300)
    worst = make("WORST", walk=10, green=5, stops=1, rent=800)
    scores = liveability_scores([best, worst])
    assert scores == {"BEST": 100.0, "WORST": 0.0}


def test_lower_rent_scores_higher_when_everything_else_is_equal():
    cheap = make("CHEAP", walk=50, green=10, stops=10, rent=300)
    pricey = make("PRICEY", walk=50, green=10, stops=10, rent=600)
    scores = liveability_scores([cheap, pricey])
    assert scores["CHEAP"] > scores["PRICEY"]
    # Only rent differs, so the gap is exactly rent's weight (0.15) times 100.
    assert scores["CHEAP"] - scores["PRICEY"] == pytest.approx(15.0)


def test_identical_suburbs_get_the_midpoint():
    a, b = make("A", 50, 10, 10, 400), make("B", 50, 10, 10, 400)
    assert liveability_scores([a, b]) == {"A": 50.0, "B": 50.0}


def test_empty_input():
    assert liveability_scores([]) == {}
    assert summarise([]) == []


def test_summary_statistics():
    stats = {s.indicator: s for s in summarise([make("A", 40, 10, 5, 400), make("B", 80, 20, 15, 600)])}
    assert stats["walk_score"].min == 40
    assert stats["walk_score"].max == 80
    assert stats["walk_score"].mean == 60
    assert stats["median_weekly_rent"].median == 500
