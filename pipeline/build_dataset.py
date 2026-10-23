"""Build a liveability dataset for Victorian SA2 areas from open government data.

Sources (all Creative Commons Attribution 4.0):
  * ABS ASGS Edition 3 (2021): SA2 boundaries and Mesh Block land use, via the ABS ArcGIS REST services
  * ABS 2021 Census General Community Profile DataPack (tables G01 and G02) for SA2, Victoria
  * Victorian Department of Transport and Planning: GTFS Schedule (public transport stops)
  * Victorian Department of Transport and Planning: Victoria Road Crash Data, via the Kaggle dataset
    nationaldigitalau/vic-road-crashes (a publicdata.au copy that adds ABS area codes to each crash)

Usage:
  python build_dataset.py                        # Greater Melbourne -> ../data/melbourne_sa2_2021.csv
                                                 # (runs every stage in stages.py; Airflow runs them as tasks)
  python build_dataset.py --gccsa 2RVIC --out ../data/rest_of_vic_sa2_2021.csv

Downloads are cached in .cache/, so re-runs are fast. Use --refresh to download them again.
Next to the CSV, a <name>.manifest.json records the provenance of the build: every source with its
version, checksum and licence, the parameters used, and each area that was excluded and why.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

log = logging.getLogger("pipeline")

ABS_ARCGIS = "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021"
CENSUS_DATAPACK_URL = (
    "https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA2_for_VIC_short-header.zip"
)
GTFS_URL = (
    "https://opendata.transport.vic.gov.au/dataset/3f4e292e-7f8a-4ffe-831f-1953be0fe448"
    "/resource/fb152201-859f-4882-9206-b768060b50ad/download/gtfs.zip"
)
# Pinned to version 3 (2026-10-12) so a rebuild always gives the same numbers. Public Kaggle datasets
# can be downloaded without an account.
CRASHES_KAGGLE_REF = "nationaldigitalau/vic-road-crashes"
CRASHES_KAGGLE_VERSION = 3
CRASHES_URL = (
    f"https://www.kaggle.com/api/v1/datasets/download/{CRASHES_KAGGLE_REF}"
    f"?datasetVersionNumber={CRASHES_KAGGLE_VERSION}"
)
USER_AGENT = "UrbanPulse-pipeline/1.0 (+https://github.com/Sri0401/project27)"

PIPELINE_VERSION = "1.2.0"
LICENCE = {"name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}
REFERENCE_YEAR = 2021
# Areas below this population are mostly industrial estates, airports or parkland. Their medians are
# unreliable or missing, so they are left out and listed in the log instead.
MIN_POPULATION = 1000
# Five complete years centred on the 2021 Census, so crashes and population describe the same period.
# Averaging over five years also smooths out the 2020 lockdown dip.
CRASH_YEARS = range(2019, 2024)

CSV_COLUMNS = [
    "code",
    "name",
    "state",
    "latitude",
    "longitude",
    "area_sqkm",
    "population",
    "median_age",
    "median_weekly_rent",
    "median_household_income",
    "green_space_pct",
    "pt_stops",
    "road_crashes_per_year",
    "reference_year",
]


@dataclass(frozen=True)
class Area:
    code: str
    name: str
    area_sqkm: float
    geometry: BaseGeometry


@dataclass(frozen=True)
class CensusFigures:
    population: int
    median_age: int
    median_weekly_rent: int
    median_household_income: int


# --- Download helpers -------------------------------------------------------------------------


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(60.0, connect=15.0),
        follow_redirects=True,
        transport=httpx.HTTPTransport(retries=3),
    )


def download(client: httpx.Client, url: str, dest: Path, refresh: bool = False) -> Path:
    """Stream a file to disk, writing to a .part file first so an interrupted download is never reused."""
    if dest.exists() and not refresh:
        log.info("Using cached %s", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Downloading %s", url)
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in response.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    log.info("Saved %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def arcgis_query(client: httpx.Client, layer: str, params: dict[str, str]) -> dict:
    response = client.get(f"{ABS_ARCGIS}/{layer}/MapServer/0/query", params=params)
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(f"ABS {layer} query failed: {body['error']}")
    if body.get("exceededTransferLimit") or body.get("properties", {}).get("exceededTransferLimit"):
        raise RuntimeError(f"ABS {layer} query returned a partial result; narrow the area")
    return body


# --- Source 1: ABS boundaries and land use ------------------------------------------------------


def fetch_areas(client: httpx.Client, gccsa: str) -> list[Area]:
    body = arcgis_query(
        client,
        "SA2",
        {
            "where": f"gccsa_code_2021='{gccsa}'",
            "outFields": "sa2_code_2021,sa2_name_2021,area_albers_sqkm",
            "outSR": "4326",
            # Simplify outlines to about 50 m. That is plenty for counting stops and keeps the response small.
            "maxAllowableOffset": "0.0005",
            "f": "geojson",
        },
    )
    areas = [
        Area(
            code=f["properties"]["sa2_code_2021"],
            name=f["properties"]["sa2_name_2021"],
            area_sqkm=float(f["properties"]["area_albers_sqkm"]),
            geometry=shape(f["geometry"]),
        )
        for f in body["features"]
        if f.get("geometry")
    ]
    log.info("Fetched %d SA2 boundaries for %s", len(areas), gccsa)
    return areas


def fetch_land_use(client: httpx.Client, gccsa: str) -> dict[str, dict[str, float]]:
    """Return {sa2 code: {mesh block category: area km2}}, summed on the ABS server."""
    body = arcgis_query(
        client,
        "MB",
        {
            "where": f"gccsa_code_2021='{gccsa}'",
            "groupByFieldsForStatistics": "sa2_code_2021,mb_category_2021",
            "outStatistics": json.dumps(
                [{"statisticType": "sum", "onStatisticField": "area_albers_sqkm", "outStatisticFieldName": "area"}]
            ),
            "f": "json",
        },
    )
    land_use: dict[str, dict[str, float]] = defaultdict(dict)
    for feature in body["features"]:
        a = feature["attributes"]
        land_use[a["sa2_code_2021"]][a["mb_category_2021"]] = float(a["area"] or 0)
    log.info("Fetched land use for %d SA2s", len(land_use))
    return dict(land_use)


def green_space_pct(categories: dict[str, float]) -> float:
    """Share of an area's land in 'Parkland' mesh blocks. Water is excluded from the total."""
    land = sum(v for k, v in categories.items() if k != "Water")
    if land <= 0:
        return 0.0
    return round(100 * categories.get("Parkland", 0.0) / land, 2)


# --- Source 2: ABS Census DataPack ------------------------------------------------------------


def _read_zip_csv(archive: zipfile.ZipFile, suffix: str) -> Iterator[dict[str, str]]:
    matches = [n for n in archive.namelist() if n.endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one file ending in {suffix}, found {matches}")
    with archive.open(matches[0]) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))


def load_census(zip_path: Path) -> dict[str, CensusFigures]:
    with zipfile.ZipFile(zip_path) as archive:
        population = {r["SA2_CODE_2021"]: int(r["Tot_P_P"]) for r in _read_zip_csv(archive, "G01_VIC_SA2.csv")}
        medians = {r["SA2_CODE_2021"]: r for r in _read_zip_csv(archive, "G02_VIC_SA2.csv")}
    figures = {
        code: CensusFigures(
            population=population[code],
            median_age=int(m["Median_age_persons"]),
            median_weekly_rent=int(m["Median_rent_weekly"]),
            median_household_income=int(m["Median_tot_hhd_inc_weekly"]),
        )
        for code, m in medians.items()
        if code in population
    }
    log.info("Loaded Census figures for %d SA2s", len(figures))
    return figures


# --- Source 3: GTFS public transport stops ----------------------------------------------------


def iter_gtfs_stops(zip_path: Path) -> Iterator[tuple[float, float]]:
    """Yield (lat, lon) for every boarding point in the Victorian GTFS bundle.

    The bundle holds one GTFS zip per transport mode (train, tram, bus and so on). Only stops and
    platforms (location_type 0 or blank) are counted, not parent stations or entrances. Points
    repeated across feeds are counted once.
    """
    seen: set[tuple[float, float]] = set()
    with zipfile.ZipFile(zip_path) as outer:
        inner_names = [n for n in outer.namelist() if n.endswith(".zip")]
        if not inner_names:
            raise RuntimeError("No per-mode GTFS zips found inside the bundle")
        for name in inner_names:
            with outer.open(name) as inner_raw, zipfile.ZipFile(io.BytesIO(inner_raw.read())) as inner:
                if "stops.txt" not in inner.namelist():
                    continue
                with inner.open("stops.txt") as stops_raw:
                    for row in csv.DictReader(io.TextIOWrapper(stops_raw, encoding="utf-8-sig")):
                        if row.get("location_type", "").strip() not in ("", "0"):
                            continue
                        point = (round(float(row["stop_lat"]), 5), round(float(row["stop_lon"]), 5))
                        if point not in seen:
                            seen.add(point)
                            yield point
    log.info("Read %d unique stops from %d GTFS feeds", len(seen), len(inner_names))


def count_stops(areas: list[Area], stops: Iterable[tuple[float, float]]) -> dict[str, int]:
    counts = dict.fromkeys((a.code for a in areas), 0)
    tree = STRtree([a.geometry for a in areas])
    for lat, lon in stops:
        # A spatial index finds candidate polygons quickly; the predicate then checks real containment.
        hits = tree.query(Point(lon, lat), predicate="intersects")
        if len(hits):
            counts[areas[int(hits[0])].code] += 1
    return counts


# --- Source 4: road crashes (Kaggle) ----------------------------------------------------------


def count_crashes(zip_path: Path, years: range = CRASH_YEARS) -> dict[str, int]:
    """Count injury crashes per SA2 over the given years.

    Each row is one crash reported to Victoria Police in which someone was injured or killed. The
    publisher has already assigned each crash to its 2021 SA2, so no spatial join is needed. The
    handful of rows marked as non-injury, and rows without a location, are skipped.
    """
    counts: dict[str, int] = defaultdict(int)
    first, last = str(years.start), str(years.stop - 1)
    with zipfile.ZipFile(zip_path) as archive:
        for row in _read_zip_csv(archive, "data.csv"):
            year = row["accident_date"][:4]
            code = row["sa2_2021_code"].strip()
            if first <= year <= last and code and row["severity"] != "Non injury accident":
                counts[code] += 1
    log.info("Counted %d injury crashes in %s-%s", sum(counts.values()), first, last)
    return dict(counts)


# --- Combine ----------------------------------------------------------------------------------


def build_rows(
    areas: list[Area],
    census: dict[str, CensusFigures],
    land_use: dict[str, dict[str, float]],
    stops: dict[str, int],
    crashes: dict[str, int],
    crash_years: int = len(CRASH_YEARS),
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    rows: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []

    def skip(area: Area, reason: str) -> None:
        skipped.append({"code": area.code, "name": area.name, "reason": reason})

    for area in sorted(areas, key=lambda a: a.name):
        figures = census.get(area.code)
        if figures is None:
            skip(area, "no Census data")
            continue
        if figures.population < MIN_POPULATION:
            skip(area, f"population {figures.population} is below {MIN_POPULATION}")
            continue
        if figures.median_weekly_rent <= 0 or figures.median_household_income <= 0:
            skip(area, "median rent or income not published")
            continue
        point = area.geometry.representative_point()  # always inside the polygon, unlike a centroid
        rows.append(
            {
                "code": area.code,
                "name": area.name,
                "state": "VIC",
                "latitude": round(point.y, 5),
                "longitude": round(point.x, 5),
                "area_sqkm": round(area.area_sqkm, 4),
                "population": figures.population,
                "median_age": figures.median_age,
                "median_weekly_rent": figures.median_weekly_rent,
                "median_household_income": figures.median_household_income,
                "green_space_pct": green_space_pct(land_use.get(area.code, {})),
                "pt_stops": stops.get(area.code, 0),
                "road_crashes_per_year": round(crashes.get(area.code, 0) / crash_years, 1),
                "reference_year": REFERENCE_YEAR,
            }
        )
    return rows, skipped


def write_csv(rows: list[dict[str, object]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    out: Path,
    rows: list[dict[str, object]],
    skipped: list[dict[str, str]],
    gccsa: str,
    sources: list[dict[str, object]],
    generated_at: datetime,
) -> dict[str, object]:
    """Describe how the dataset was built, so any figure can be traced back to its inputs."""
    return {
        "dataset": out.stem,
        "generated_at": generated_at.isoformat(),
        "pipeline_version": PIPELINE_VERSION,
        "output": {
            "file": out.name,
            "sha256": sha256_of(out),
            "rows": len(rows),
            "columns": CSV_COLUMNS,
        },
        "parameters": {
            "gccsa": gccsa,
            "min_population": MIN_POPULATION,
            "crash_years": [CRASH_YEARS.start, CRASH_YEARS.stop - 1],
            "reference_year": REFERENCE_YEAR,
        },
        "sources": sources,
        "licence": LICENCE,
        "skipped": skipped,
    }


def write_manifest(manifest: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gccsa", default="2GMEL", help="ABS Greater Capital City code in Victoria (2GMEL or 2RVIC)")
    parser.add_argument("--out", type=Path, default=here.parent / "data" / "melbourne_sa2_2021.csv")
    parser.add_argument("--cache-dir", type=Path, default=here / ".cache")
    parser.add_argument("--refresh", action="store_true", help="download cached files again")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.gccsa.startswith("2"):
        parser.error("Only Victorian areas are supported, because the Census and GTFS inputs cover Victoria")

    # Imported here because stages.py imports this module.
    from stages import Paths, run_all

    paths = Paths(cache_dir=args.cache_dir, work_dir=args.cache_dir / "work", out=args.out)
    run_all(paths, args.gccsa, refresh=args.refresh)
    log.info("Attribution: data from the ABS and DTP Victoria (crashes via Kaggle), CC BY 4.0 - see NOTICE.md")


if __name__ == "__main__":
    main()
