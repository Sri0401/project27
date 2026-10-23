"""Structure tests for the Airflow DAG. Skipped when Airflow is not installed (for example on
Windows, where Airflow does not run); CI runs them in a dedicated job."""

from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.models import DagBag  # noqa: E402

DAGS = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=DAGS)  # AIRFLOW__CORE__LOAD_EXAMPLES=False keeps example DAGs out


@pytest.fixture(scope="module")
def dag(dagbag):
    return dagbag.dags["urbanpulse_dataset"]  # parsed DAG, no metadata database needed


def test_dag_imports_without_errors(dagbag):
    assert dagbag.import_errors == {}
    assert "urbanpulse_dataset" in dagbag.dag_ids


def test_dag_settings(dag):
    assert dag.schedule == "@weekly"
    assert dag.catchup is False
    assert dag.max_active_runs == 1


def test_task_dependencies(dag):
    expected_upstream = {
        "extract_boundaries": set(),
        "extract_land_use": set(),
        "download_census": set(),
        "download_gtfs": set(),
        "download_crashes": set(),
        "transform_census": {"download_census"},
        "count_stops": {"extract_boundaries", "download_gtfs"},
        "count_crashes": {"download_crashes"},
        "build_candidate": {
            "extract_boundaries",
            "extract_land_use",
            "transform_census",
            "count_stops",
            "count_crashes",
        },
        "quality_checks": {"build_candidate"},
        "publish": {"quality_checks"},
    }
    actual = {t.task_id: set(t.upstream_task_ids) for t in dag.tasks}
    assert actual == expected_upstream


def test_retries_except_quality_gate(dag):
    retries = {t.task_id: t.retries for t in dag.tasks}
    assert retries.pop("quality_checks") == 0
    assert set(retries.values()) == {2}
