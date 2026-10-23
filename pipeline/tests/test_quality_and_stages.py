import json
from pathlib import Path

import pytest
from shapely.geometry import box, mapping

import quality
import stages
from build_dataset import CSV_COLUMNS


def good_row(code: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "code": code,
        "name": f"Area {code}",
        "state": "VIC",
        "latitude": -37.8,
        "longitude": 145.0,
        "area_sqkm": 2.5,
        "population": 5000,
        "median_age": 35,
        "median_weekly_rent": 420,
        "median_household_income": 1900,
        "green_space_pct": 12.5,
        "pt_stops": 30,
        "road_crashes_per_year": 8.4,
        "reference_year": 2021,
    }
    return row | overrides


def failed(rows: list[dict[str, object]], areas_fetched: int | None = None) -> set[str]:
    results = quality.run_checks(rows, areas_fetched or len(rows))
    return {r.name for r in results if not r.passed}


def test_clean_rows_pass_every_check():
    assert failed([good_row(str(i)) for i in range(20)]) == set()


@pytest.mark.parametrize(
    ("rows", "areas_fetched", "expected"),
    [
        ([good_row("1"), good_row("1")], 2, "codes_unique"),
        ([good_row("1", latitude=145.0, longitude=-37.8)], 1, "points_inside_victoria"),  # swapped lat/lon
        ([good_row("1", green_space_pct=140)], 1, "values_in_range"),
        ([good_row("1", population=10)], 1, "values_in_range"),
        ([good_row("1", name="")], 1, "no_blank_values"),
        ([good_row(str(i)) for i in range(5)], 10, "enough_areas_published"),
        ([], 10, "enough_areas_published"),
    ],
)
def test_each_check_catches_its_failure(rows, areas_fetched, expected):
    assert expected in failed(rows, areas_fetched)


def test_broken_spatial_join_is_caught():
    # Every area with zero stops means the stop-to-area join failed silently.
    rows = [good_row(str(i), pt_stops=0) for i in range(20)]
    assert failed(rows) == {"stops_joined"}


def test_assert_quality_reports_all_failures_at_once():
    with pytest.raises(quality.DataQualityError) as e:
        quality.assert_quality([good_row("1", pt_stops=0, road_crashes_per_year=0)], 1)
    assert {f.name for f in e.value.failures} == {"stops_joined", "crashes_joined"}


# --- Stages: build -> quality gate -> publish, using synthetic intermediate files -----------------


@pytest.fixture
def paths(tmp_path: Path) -> stages.Paths:
    p = stages.Paths(cache_dir=tmp_path / "cache", work_dir=tmp_path / "work", out=tmp_path / "out" / "areas.csv")
    p.cache_dir.mkdir()
    for name in ("census_gcp_sa2_vic.zip", "gtfs_vic.zip", "vic_road_crashes_v3.zip"):
        (p.cache_dir / name).write_bytes(b"source file " + name.encode())

    codes = [f"2{i:02d}" for i in range(12)]
    features = [
        {
            "type": "Feature",
            "properties": {"code": c, "name": f"Area {c}", "area_sqkm": 3.0},
            "geometry": mapping(box(145.0, -37.9, 145.05, -37.85)),
        }
        for c in codes
    ]
    features.append(  # an area with too few residents, which build_rows must skip
        {
            "type": "Feature",
            "properties": {"code": "299", "name": "Airport", "area_sqkm": 9.0},
            "geometry": mapping(box(144.8, -37.7, 144.9, -37.6)),
        }
    )
    census = {
        c: {"population": 6000, "median_age": 36, "median_weekly_rent": 400, "median_household_income": 1800}
        for c in codes
    }
    census["299"] = {"population": 15, "median_age": 40, "median_weekly_rent": 0, "median_household_income": 0}
    files = {
        "areas.geojson": {"type": "FeatureCollection", "features": features},
        "land_use.json": {c: {"Parkland": 1.0, "Residential": 2.0} for c in codes},
        "census.json": census,
        "stops.json": {c: 25 for c in codes},
        "crashes.json": {c: 40 for c in codes},
    }
    for name, data in files.items():
        p.work(name).write_text(json.dumps(data), encoding="utf-8")
    return p


def test_build_check_publish(paths):
    assert stages.build_candidate(paths) == {"rows": 12, "skipped": 1}
    report = stages.check_quality(paths)
    assert all(r["passed"] for r in report)

    stages.publish(paths, "2GMEL")
    assert paths.out.read_text(encoding="utf-8").splitlines()[0] == ",".join(CSV_COLUMNS)
    manifest = json.loads(paths.out.with_name("areas.manifest.json").read_text(encoding="utf-8"))
    assert manifest["output"]["rows"] == 12
    assert manifest["skipped"] == [{"code": "299", "name": "Airport", "reason": "population 15 is below 1000"}]
    crash_source = next(s for s in manifest["sources"] if s["retrieved_via"] == "Kaggle API")
    assert crash_source["records_used"] == 12 * 40
    assert len(crash_source["sha256"]) == 64


def test_publish_refuses_without_passing_quality_checks(paths):
    stages.build_candidate(paths)
    with pytest.raises(RuntimeError, match="quality checks have not passed"):
        stages.publish(paths, "2GMEL")
    assert not paths.out.exists()


def test_failed_quality_check_blocks_publish(paths):
    paths.work("stops.json").write_text(json.dumps({}), encoding="utf-8")  # simulate a broken stop join
    stages.build_candidate(paths)
    with pytest.raises(quality.DataQualityError, match="stops_joined"):
        stages.check_quality(paths)
    with pytest.raises(RuntimeError):
        stages.publish(paths, "2GMEL")


def test_each_candidate_needs_its_own_quality_pass(paths):
    stages.build_candidate(paths)
    stages.check_quality(paths)
    stages.publish(paths, "2GMEL")
    stages.build_candidate(paths)  # a new candidate
    with pytest.raises(RuntimeError):
        stages.publish(paths, "2GMEL")


def test_missing_upstream_output_gives_a_clear_error(paths):
    paths.work("census.json").unlink()
    with pytest.raises(FileNotFoundError, match="census.json is missing"):
        stages.build_candidate(paths)
