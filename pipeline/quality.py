"""Data-quality checks that run before a dataset is published.

Each check guards against a real way the pipeline could fail silently. For example, if every area
ended up with zero transport stops, the spatial join would have broken without raising an error.
A failed check stops the run, so the previous dataset stays in place.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

from build_dataset import CSV_COLUMNS, MIN_POPULATION

# Generous box around Victoria, so a swapped latitude/longitude or wrong projection is caught.
VIC_LAT = (-39.3, -33.9)
VIC_LON = (140.9, 150.1)
# Share of published areas that must have at least one stop / one crash. Real data is far above
# these (over 99%); a value near zero means a join or a source file is broken.
MIN_SHARE_WITH_STOPS = 0.9
MIN_SHARE_WITH_CRASHES = 0.9
# The pipeline may exclude a few areas (airports, parks), but never most of them.
MIN_SHARE_PUBLISHED = 0.9


class DataQualityError(Exception):
    def __init__(self, failures: list[CheckResult]) -> None:
        self.failures = failures
        super().__init__("; ".join(f"{f.name}: {f.detail}" for f in failures))


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def _share(rows: list[dict[str, object]], predicate: Callable[[dict[str, object]], bool]) -> float:
    return sum(1 for r in rows if predicate(r)) / len(rows) if rows else 0.0


def run_checks(rows: list[dict[str, object]], areas_fetched: int) -> list[CheckResult]:
    """Check rows as written to the CSV (values may be strings or numbers)."""

    def num(row: dict[str, object], column: str) -> float:
        return float(row[column])  # type: ignore[arg-type]

    results: list[CheckResult] = []

    def check(name: str, passed: bool, detail: str) -> None:
        results.append(CheckResult(name, passed, detail))

    published = len(rows) / areas_fetched if areas_fetched else 0.0
    check(
        "enough_areas_published",
        bool(rows) and published >= MIN_SHARE_PUBLISHED,
        f"{len(rows)} of {areas_fetched} areas ({published:.0%}); minimum {MIN_SHARE_PUBLISHED:.0%}",
    )

    missing = [c for c in CSV_COLUMNS if rows and c not in rows[0]]
    check("schema_matches", not missing, f"missing columns: {missing}" if missing else "all columns present")

    blanks = sorted({c for r in rows for c in CSV_COLUMNS if str(r.get(c, "")).strip() == ""})
    check("no_blank_values", not blanks, f"blank values in: {blanks}" if blanks else "no blanks")

    codes = [str(r["code"]) for r in rows]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    check("codes_unique", not dupes, f"duplicate codes: {dupes[:5]}" if dupes else f"{len(codes)} unique codes")

    try:
        out_of_box = [
            r["code"]
            for r in rows
            if not (VIC_LAT[0] <= num(r, "latitude") <= VIC_LAT[1] and VIC_LON[0] <= num(r, "longitude") <= VIC_LON[1])
        ]
        check(
            "points_inside_victoria",
            not out_of_box,
            f"outside Victoria: {out_of_box[:5]}" if out_of_box else "all points in Victoria",
        )

        bad_ranges = [
            r["code"]
            for r in rows
            if num(r, "population") < MIN_POPULATION
            or not 0 <= num(r, "green_space_pct") <= 100
            or num(r, "median_weekly_rent") <= 0
            or num(r, "median_household_income") <= 0
            or num(r, "area_sqkm") <= 0
            or num(r, "pt_stops") < 0
            or num(r, "road_crashes_per_year") < 0
        ]
        check(
            "values_in_range",
            not bad_ranges,
            f"out-of-range rows: {bad_ranges[:5]}" if bad_ranges else "all values in range",
        )

        with_stops = _share(rows, lambda r: num(r, "pt_stops") > 0)
        check(
            "stops_joined",
            with_stops >= MIN_SHARE_WITH_STOPS,
            f"{with_stops:.1%} of areas have stops; minimum {MIN_SHARE_WITH_STOPS:.0%}",
        )

        with_crashes = _share(rows, lambda r: num(r, "road_crashes_per_year") > 0)
        check(
            "crashes_joined",
            with_crashes >= MIN_SHARE_WITH_CRASHES,
            f"{with_crashes:.1%} of areas have crashes; minimum {MIN_SHARE_WITH_CRASHES:.0%}",
        )
    except (KeyError, ValueError) as e:
        check("values_numeric", False, f"non-numeric or missing value: {e}")

    return results


def assert_quality(rows: list[dict[str, object]], areas_fetched: int) -> list[dict[str, object]]:
    """Run every check and raise DataQualityError listing all failures. Returns a report."""
    results = run_checks(rows, areas_fetched)
    failures = [r for r in results if not r.passed]
    if failures:
        raise DataQualityError(failures)
    return [asdict(r) for r in results]
