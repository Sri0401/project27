"""
### UrbanPulse dataset pipeline

Builds the Greater Melbourne liveability dataset (`data/melbourne_sa2_2021.csv`) from open
government data, once a week.

1. **Extract**, in parallel: ABS SA2 boundaries and land use (ArcGIS REST API), the ABS Census
   DataPack and the Victorian GTFS timetable (file downloads), and road crash data (Kaggle API).
2. **Transform**: join Census figures, count transport stops inside each area (spatial join), and
   count injury crashes per area.
3. **Build** the candidate dataset, then run the **quality checks**. If a check fails, the run
   stops here and the previously published dataset stays in place.
4. **Publish** the CSV and its provenance manifest, which the API records in MongoDB.

Each task runs one function from `pipeline/stages.py`. The command-line pipeline
(`python build_dataset.py`) runs the same functions in sequence. Downloads are cached, so a weekly
run only fetches what changed. Use the `refresh` parameter to force fresh downloads.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import Param, dag, task

# Make pipeline/ importable: stages.py and build_dataset.py live next to this dags/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stages  # noqa: E402

GCCSA = "2GMEL"  # ABS Greater Capital City Statistical Area: Greater Melbourne


@dag(
    dag_id="urbanpulse_dataset",
    description="Build the Greater Melbourne liveability dataset from ABS, DTP and Kaggle open data",
    schedule="@weekly",
    start_date=pendulum.datetime(2026, 10, 1, tz="Australia/Melbourne"),
    catchup=False,
    max_active_runs=1,  # runs share the work directory, so never overlap them
    default_args={
        # Government APIs and large downloads occasionally fail; retry with growing waits.
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "execution_timeout": timedelta(minutes=30),
    },
    params={"refresh": Param(False, type="boolean", description="Download source files again")},
    tags=["urbanpulse", "open-data", "etl"],
    doc_md=__doc__,
)
def urbanpulse_dataset():
    paths = stages.Paths.from_env

    # --- Extract (no dependencies between these, so they run in parallel) --------------------

    @task
    def extract_boundaries() -> int:
        return stages.extract_boundaries(paths(), GCCSA)

    @task
    def extract_land_use() -> int:
        return stages.extract_land_use(paths(), GCCSA)

    @task
    def download_census(params: dict | None = None) -> str:
        return stages.download_census(paths(), refresh=bool(params and params["refresh"]))

    @task
    def download_gtfs(params: dict | None = None) -> str:
        return stages.download_gtfs(paths(), refresh=bool(params and params["refresh"]))

    @task
    def download_crashes(params: dict | None = None) -> str:
        return stages.download_crashes(paths(), refresh=bool(params and params["refresh"]))

    # --- Transform. Each task takes its upstream result, which sets the dependency. --------

    @task
    def transform_census(census_zip: str) -> int:
        return stages.transform_census(paths())

    @task
    def count_stops(area_count: int, gtfs_zip: str) -> int:
        return stages.transform_stops(paths())

    @task
    def count_crashes(crashes_zip: str) -> int:
        return stages.transform_crashes(paths())

    @task
    def build_candidate(areas: int, land_use: int, census: int, stops: int, crashes: int) -> dict:
        return stages.build_candidate(paths())

    # --- Quality gate and publish ------------------------------------------------------------

    @task(retries=0)  # a failed check is a data problem, so retrying would not help
    def quality_checks(candidate: dict) -> int:
        return len(stages.check_quality(paths()))

    @task
    def publish(checks_passed: int) -> str:
        return stages.publish(paths(), GCCSA)

    areas = extract_boundaries()
    land_use = extract_land_use()
    census = transform_census(download_census())
    stops = count_stops(areas, download_gtfs())
    crashes = count_crashes(download_crashes())
    candidate = build_candidate(areas, land_use, census, stops, crashes)
    publish(quality_checks(candidate))


urbanpulse_dataset()
