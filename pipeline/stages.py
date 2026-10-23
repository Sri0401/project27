"""Pipeline stages.

Each stage reads its inputs from, and writes its output to, a work directory. That lets the
stages run as separate processes, as Airflow tasks do (see dags/urbanpulse_dataset.py), or one
after another from the command line (python build_dataset.py). Both paths run this same code.

Stage outputs in the work directory:
  areas.geojson   SA2 boundaries          land_use.json   land-use area per SA2
  census.json     Census figures per SA2  stops.json      transport stops per SA2
  crashes.json    injury crashes per SA2  candidate.csv   dataset awaiting quality checks
  quality.json    quality-check report
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from shapely.geometry import mapping, shape

import quality
from build_dataset import (
    ABS_ARCGIS,
    CENSUS_DATAPACK_URL,
    CRASHES_KAGGLE_REF,
    CRASHES_KAGGLE_VERSION,
    CRASHES_URL,
    GTFS_URL,
    LICENCE,
    Area,
    CensusFigures,
    build_manifest,
    build_rows,
    count_crashes,
    count_stops,
    download,
    fetch_areas,
    fetch_land_use,
    iter_gtfs_stops,
    load_census,
    make_client,
    sha256_of,
    write_csv,
    write_manifest,
)

log = logging.getLogger("pipeline.stages")

PIPELINE_DIR = Path(__file__).resolve().parent
ABS_PUBLISHER = "Australian Bureau of Statistics"
DTP_PUBLISHER = "Department of Transport and Planning (Victoria)"


@dataclass(frozen=True)
class Paths:
    cache_dir: Path  # downloaded source files, reused between runs
    work_dir: Path  # intermediate files for the current run
    out: Path  # published CSV; the manifest is written next to it

    @classmethod
    def from_env(cls) -> Paths:
        cache = Path(os.getenv("URBANPULSE_CACHE_DIR", PIPELINE_DIR / ".cache"))
        return cls(
            cache_dir=cache,
            work_dir=Path(os.getenv("URBANPULSE_WORK_DIR", cache / "work")),
            out=Path(os.getenv("URBANPULSE_OUTPUT", PIPELINE_DIR.parent / "data" / "melbourne_sa2_2021.csv")),
        )

    @property
    def census_zip(self) -> Path:
        return self.cache_dir / "census_gcp_sa2_vic.zip"

    @property
    def gtfs_zip(self) -> Path:
        return self.cache_dir / "gtfs_vic.zip"

    @property
    def crashes_zip(self) -> Path:
        return self.cache_dir / f"vic_road_crashes_v{CRASHES_KAGGLE_VERSION}.zip"

    def work(self, name: str) -> Path:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        return self.work_dir / name


def _write_json(path: Path, data: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)  # atomic, so a half-written file is never read by the next task


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path.name} is missing; its upstream stage has not run")
    return json.loads(path.read_text(encoding="utf-8"))


# --- Extract ------------------------------------------------------------------------------------


def extract_boundaries(paths: Paths, gccsa: str) -> int:
    with make_client() as client:
        areas = fetch_areas(client, gccsa)
    features = [
        {
            "type": "Feature",
            "properties": {"code": a.code, "name": a.name, "area_sqkm": a.area_sqkm},
            "geometry": mapping(a.geometry),
        }
        for a in areas
    ]
    _write_json(paths.work("areas.geojson"), {"type": "FeatureCollection", "features": features})
    return len(areas)


def extract_land_use(paths: Paths, gccsa: str) -> int:
    with make_client() as client:
        land_use = fetch_land_use(client, gccsa)
    _write_json(paths.work("land_use.json"), land_use)
    return len(land_use)


def download_census(paths: Paths, refresh: bool = False) -> str:
    with make_client() as client:
        return str(download(client, CENSUS_DATAPACK_URL, paths.census_zip, refresh))


def download_gtfs(paths: Paths, refresh: bool = False) -> str:
    with make_client() as client:
        return str(download(client, GTFS_URL, paths.gtfs_zip, refresh))


def download_crashes(paths: Paths, refresh: bool = False) -> str:
    with make_client() as client:
        return str(download(client, CRASHES_URL, paths.crashes_zip, refresh))


# --- Transform ----------------------------------------------------------------------------------


def load_areas(paths: Paths) -> list[Area]:
    collection = _read_json(paths.work("areas.geojson"))
    return [
        Area(f["properties"]["code"], f["properties"]["name"], f["properties"]["area_sqkm"], shape(f["geometry"]))
        for f in collection["features"]
    ]


def transform_census(paths: Paths) -> int:
    census = load_census(paths.census_zip)
    _write_json(paths.work("census.json"), {code: asdict(f) for code, f in census.items()})
    return len(census)


def transform_stops(paths: Paths) -> int:
    stops = count_stops(load_areas(paths), iter_gtfs_stops(paths.gtfs_zip))
    _write_json(paths.work("stops.json"), stops)
    return sum(stops.values())


def transform_crashes(paths: Paths) -> int:
    crashes = count_crashes(paths.crashes_zip)
    _write_json(paths.work("crashes.json"), crashes)
    return sum(crashes.values())


def build_candidate(paths: Paths) -> dict[str, int]:
    """Join everything into the candidate CSV. It is only published after the quality checks."""
    census = {code: CensusFigures(**f) for code, f in _read_json(paths.work("census.json")).items()}
    rows, skipped = build_rows(
        load_areas(paths),
        census,
        _read_json(paths.work("land_use.json")),
        _read_json(paths.work("stops.json")),
        _read_json(paths.work("crashes.json")),
    )
    for s in skipped:
        log.info("Skipped %s (%s): %s", s["name"], s["code"], s["reason"])
    write_csv(rows, paths.work("candidate.csv"))
    _write_json(paths.work("skipped.json"), skipped)
    return {"rows": len(rows), "skipped": len(skipped)}


# --- Quality gate and publish -------------------------------------------------------------------


def _read_candidate(paths: Paths) -> list[dict[str, object]]:
    with paths.work("candidate.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_quality(paths: Paths) -> list[dict[str, object]]:
    areas_fetched = len(_read_json(paths.work("areas.geojson"))["features"])
    report = quality.assert_quality(_read_candidate(paths), areas_fetched)
    _write_json(paths.work("quality.json"), report)
    log.info("All %d quality checks passed", len(report))
    return report


def publish(paths: Paths, gccsa: str) -> str:
    """Copy the checked candidate into place and write its provenance manifest."""
    if not paths.work("quality.json").exists():
        raise RuntimeError("Refusing to publish: the quality checks have not passed for this candidate")
    paths.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(paths.work("candidate.csv"), paths.out)

    rows = _read_candidate(paths)
    sources: list[dict[str, object]] = [
        {
            "name": "ABS ASGS 2021 SA2 boundaries",
            "publisher": ABS_PUBLISHER,
            "url": f"{ABS_ARCGIS}/SA2/MapServer",
            "retrieved_via": "ArcGIS REST API",
            "records_used": len(_read_json(paths.work("areas.geojson"))["features"]),
        },
        {
            "name": "ABS ASGS 2021 Mesh Block land use (aggregated by SA2 on the server)",
            "publisher": ABS_PUBLISHER,
            "url": f"{ABS_ARCGIS}/MB/MapServer",
            "retrieved_via": "ArcGIS REST API",
            "records_used": len(_read_json(paths.work("land_use.json"))),
        },
        {
            "name": "ABS 2021 Census GCP DataPack, SA2, Victoria (G01, G02)",
            "publisher": ABS_PUBLISHER,
            "url": CENSUS_DATAPACK_URL,
            "retrieved_via": "file download",
            "sha256": sha256_of(paths.census_zip),
            "records_used": len(_read_json(paths.work("census.json"))),
        },
        {
            "name": "Victorian GTFS Schedule",
            "publisher": DTP_PUBLISHER,
            "url": GTFS_URL,
            "retrieved_via": "file download",
            "sha256": sha256_of(paths.gtfs_zip),
            "records_used": sum(_read_json(paths.work("stops.json")).values()),
        },
        {
            "name": "Victoria Road Crash Data",
            "publisher": DTP_PUBLISHER,
            "url": f"https://www.kaggle.com/datasets/{CRASHES_KAGGLE_REF}",
            "retrieved_via": "Kaggle API",
            "version": CRASHES_KAGGLE_VERSION,
            "sha256": sha256_of(paths.crashes_zip),
            "records_used": sum(_read_json(paths.work("crashes.json")).values()),
        },
    ]
    for source in sources:
        source["licence"] = LICENCE["name"]

    manifest = build_manifest(
        out=paths.out,
        rows=rows,
        skipped=_read_json(paths.work("skipped.json")),
        gccsa=gccsa,
        sources=sources,
        generated_at=datetime.now(UTC),
    )
    manifest_path = paths.out.with_name(f"{paths.out.stem}.manifest.json")
    write_manifest(manifest, manifest_path)
    paths.work("quality.json").unlink()  # the next candidate must pass its own checks
    log.info("Published %d areas to %s with manifest %s", len(rows), paths.out, manifest_path.name)
    return str(paths.out)


def run_all(paths: Paths, gccsa: str, refresh: bool = False) -> str:
    """Run every stage in order. Airflow runs the same stages as separate tasks."""
    extract_boundaries(paths, gccsa)
    extract_land_use(paths, gccsa)
    download_census(paths, refresh)
    download_gtfs(paths, refresh)
    download_crashes(paths, refresh)
    transform_census(paths)
    transform_stops(paths)
    transform_crashes(paths)
    build_candidate(paths)
    check_quality(paths)
    return publish(paths, gccsa)
