import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime

import pytest
from shapely.geometry import Point, box

from build_dataset import (
    CSV_COLUMNS,
    Area,
    CensusFigures,
    build_manifest,
    build_rows,
    count_crashes,
    count_stops,
    green_space_pct,
    iter_gtfs_stops,
    load_census,
    write_csv,
    write_manifest,
)


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buffer.getvalue()


def test_green_space_excludes_water_from_total():
    assert green_space_pct({"Parkland": 1.0, "Residential": 3.0, "Water": 10.0}) == 25.0
    assert green_space_pct({"Residential": 2.0}) == 0.0
    assert green_space_pct({}) == 0.0


def test_gtfs_reads_nested_feeds_skips_stations_and_dedupes(tmp_path):
    header = "stop_id,stop_name,stop_lat,stop_lon,location_type\n"
    tram = make_zip({"stops.txt": (header + "1,A,-37.8,145.0,0\n2,Station,-37.9,145.1,1\n").encode()})
    bus = make_zip(
        {
            "stops.txt": (header + "3,A again,-37.8,145.0,\n4,B,-37.7,144.9,\n").encode(),
            "routes.txt": b"route_id\n",
        }
    )
    bundle = tmp_path / "gtfs.zip"
    bundle.write_bytes(make_zip({"3/google_transit.zip": tram, "4/google_transit.zip": bus}))

    assert sorted(iter_gtfs_stops(bundle)) == [(-37.8, 145.0), (-37.7, 144.9)]


def test_count_stops_assigns_points_to_containing_area():
    areas = [
        Area("A", "West", 1.0, box(144.0, -38.0, 145.0, -37.0)),
        Area("B", "East", 1.0, box(145.0, -38.0, 146.0, -37.0)),
    ]
    # (lat, lon) pairs: two in West, one in East, one outside both.
    stops = [(-37.5, 144.5), (-37.2, 144.1), (-37.5, 145.5), (-30.0, 150.0)]
    assert count_stops(areas, stops) == {"A": 2, "B": 1}


def test_load_census_joins_population_and_medians(tmp_path):
    folder = "2021 Census GCP Statistical Area 2 for VIC/"
    pack = tmp_path / "census.zip"
    pack.write_bytes(
        make_zip(
            {
                folder + "2021Census_G01_VIC_SA2.csv": b"SA2_CODE_2021,Tot_P_P\n201,5000\n202,40\n",
                folder + "2021Census_G02_VIC_SA2.csv": (
                    b"SA2_CODE_2021,Median_age_persons,Median_rent_weekly,Median_tot_hhd_inc_weekly\n"
                    b"201,35,400,1800\n202,50,0,0\n"
                ),
            }
        )
    )
    census = load_census(pack)
    assert census["201"] == CensusFigures(5000, 35, 400, 1800)
    assert census["202"].population == 40


def test_build_rows_filters_unreliable_areas_and_places_point_inside():
    square = box(145.0, -38.0, 145.1, -37.9)
    areas = [
        Area("1", "Good", 10.0, square),
        Area("2", "Tiny", 1.0, square),
        Area("3", "No rent", 1.0, square),
        Area("4", "Missing", 1.0, square),
    ]
    census = {
        "1": CensusFigures(5000, 35, 400, 1800),
        "2": CensusFigures(20, 40, 300, 1500),
        "3": CensusFigures(3000, 40, 0, 1500),
    }
    rows, skipped = build_rows(
        areas, census, {"1": {"Parkland": 1, "Residential": 3}}, {"1": 7}, {"1": 52}, crash_years=5
    )

    assert [r["code"] for r in rows] == ["1"]
    row = rows[0]
    assert row["green_space_pct"] == 25.0
    assert row["pt_stops"] == 7
    assert row["road_crashes_per_year"] == 10.4
    assert square.contains(Point(row["longitude"], row["latitude"]))
    assert [s["code"] for s in skipped] == ["4", "3", "2"]  # sorted by name: Missing, No rent, Tiny
    assert skipped[2] == {"code": "2", "name": "Tiny", "reason": "population 20 is below 1000"}


@pytest.mark.parametrize("value", ["", "0"])
def test_blank_and_zero_location_types_both_count_as_stops(tmp_path, value):
    feed = make_zip({"stops.txt": f"stop_id,stop_lat,stop_lon,location_type\n1,-37.8,145.0,{value}\n".encode()})
    bundle = tmp_path / "gtfs.zip"
    bundle.write_bytes(make_zip({"1/google_transit.zip": feed}))
    assert list(iter_gtfs_stops(bundle)) == [(-37.8, 145.0)]


def test_csv_round_trip_quotes_names_with_commas(tmp_path):
    row = dict.fromkeys(CSV_COLUMNS, 1) | {"name": "Smith, North"}
    out = tmp_path / "out.csv"
    write_csv([row], out)
    assert next(csv.DictReader(out.open()))["name"] == "Smith, North"


def test_count_crashes_filters_years_severity_and_missing_area(tmp_path):
    header = "accident_no,accident_date,severity,sa2_2021_code\n"
    body = (
        "T1,2019-01-05,Serious injury accident,201\n"
        "T2,2023-12-31,Other injury accident,201\n"
        "T3,2021-06-01,Fatal accident,202\n"
        "T4,2018-12-31,Other injury accident,201\n"  # before the window
        "T5,2024-01-01,Other injury accident,201\n"  # after the window
        "T6,2020-03-03,Non injury accident,201\n"  # not an injury crash
        "T7,2020-03-03,Other injury accident,\n"  # no location
    )
    bundle = tmp_path / "crashes.zip"
    bundle.write_bytes(make_zip({"data.csv": (header + body).encode(), "publicdata.json": b"{}"}))

    assert count_crashes(bundle, range(2019, 2024)) == {"201": 2, "202": 1}


def test_manifest_records_output_checksum_parameters_and_skips(tmp_path):
    out = tmp_path / "areas_2021.csv"
    row = dict.fromkeys(CSV_COLUMNS, 1)
    write_csv([row], out)
    skipped = [{"code": "9", "name": "Airport", "reason": "population 0 is below 1000"}]
    when = datetime(2026, 10, 20, tzinfo=UTC)

    manifest = build_manifest(
        out=out, rows=[row], skipped=skipped, gccsa="2GMEL", sources=[{"name": "x"}], generated_at=when
    )

    assert manifest["dataset"] == "areas_2021"
    assert manifest["generated_at"] == "2026-10-20T00:00:00+00:00"
    assert manifest["output"]["rows"] == 1
    assert manifest["output"]["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert manifest["parameters"]["crash_years"] == [2019, 2023]
    assert manifest["skipped"] == skipped
    assert manifest["licence"]["url"] == "https://creativecommons.org/licenses/by/4.0/"

    path = tmp_path / "areas_2021.manifest.json"
    write_manifest(manifest, path)
    assert json.loads(path.read_text()) == manifest
