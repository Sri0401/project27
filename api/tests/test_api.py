from app.config import Settings
from app.repositories import InMemorySuburbRepository

from .conftest import TEST_API_KEY

NEW_DATASET = {
    "slug": "test-dataset",
    "title": "Test dataset",
    "publisher": "Unit tests",
    "licence": "CC0",
    "url": "https://example.org/data",
    "tags": ["test"],
}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "backend": "memory",
        "checks": {"suburb_store": True, "dataset_store": True},
    }


def test_list_sorted_by_score_by_default(client):
    body = client.get("/api/suburbs").json()
    assert len(body) == 5
    scores = [s["liveability_score"] for s in body]
    assert scores == sorted(scores, reverse=True)


def test_derived_fields_in_response(client):
    inner = client.get("/api/suburbs/A1").json()
    assert inner["population_density"] == 10000.0
    assert inner["pt_stops_per_sqkm"] == 40.0
    assert inner["rent_to_income_pct"] == 25.0
    assert inner["crashes_per_1000_residents"] == 3.0  # 60 crashes a year / 20,000 residents
    assert 0 <= inner["liveability_score"] <= 100


def test_filters_and_sorting(client):
    body = client.get(
        "/api/suburbs", params={"min_green_space": 10, "max_rent": 450, "sort_by": "name", "order": "asc"}
    ).json()
    assert [s["code"] for s in body] == ["A2", "A3"]


def test_name_search_is_case_insensitive(client):
    body = client.get("/api/suburbs", params={"q": "pricey"}).json()
    assert [s["name"] for s in body] == ["Pricey, E"]


def test_scores_do_not_change_when_filtering(client):
    everything = {s["code"]: s["liveability_score"] for s in client.get("/api/suburbs").json()}
    filtered = client.get("/api/suburbs", params={"min_green_space": 15}).json()
    assert filtered
    assert all(s["liveability_score"] == everything[s["code"]] for s in filtered)


def test_invalid_query_is_rejected(client):
    assert client.get("/api/suburbs", params={"min_green_space": 101}).status_code == 422
    assert client.get("/api/suburbs", params={"sort_by": "password"}).status_code == 422


def test_get_area_is_case_insensitive_and_404s(client):
    assert client.get("/api/suburbs/a4").json()["name"] == "Cheap D"
    assert client.get("/api/suburbs/NOPE").status_code == 404


def test_geojson(client):
    body = client.get("/api/suburbs/geojson").json()
    assert body["type"] == "FeatureCollection"
    inner = next(f for f in body["features"] if f["id"] == "A1")
    assert inner["geometry"] == {"type": "Point", "coordinates": [144.97, -37.8]}
    assert "liveability_score" in inner["properties"]


def test_indicator_summary(client):
    body = client.get("/api/indicators/summary").json()
    assert body["suburb_count"] == 5
    assert body["total_population"] == 86000
    green = next(i for i in body["indicators"] if i["indicator"] == "green_space_pct")
    assert green["min"] == 2 and green["max"] == 40


def test_latest_ingestion(client):
    body = client.get("/api/ingestion/latest").json()
    assert body["source"] == "areas.csv"
    assert body["rows_loaded"] == 5


def test_seeded_datasets_and_tag_filter(client):
    assert len(client.get("/api/datasets").json()) == 6
    transport = client.get("/api/datasets", params={"tag": "transport"}).json()
    assert [d["slug"] for d in transport] == ["ptv-gtfs-timetable"]


def test_register_dataset_requires_valid_key(client):
    assert client.post("/api/datasets", json=NEW_DATASET).status_code == 401
    wrong = client.post("/api/datasets", json=NEW_DATASET, headers={"X-API-Key": "wrong"})
    assert wrong.status_code == 401


def test_register_dataset(client):
    headers = {"X-API-Key": TEST_API_KEY}
    r = client.post("/api/datasets", json=NEW_DATASET, headers=headers)
    assert r.status_code == 201
    assert "registered_at" in r.json()
    assert client.post("/api/datasets", json=NEW_DATASET, headers=headers).status_code == 409


def test_register_dataset_validates_body(client):
    bad = {**NEW_DATASET, "slug": "Bad Slug!", "url": "javascript:alert(1)"}
    r = client.post("/api/datasets", json=bad, headers={"X-API-Key": TEST_API_KEY})
    assert r.status_code == 422


def test_writes_disabled_without_configured_key(client_without_key):
    r = client_without_key.post("/api/datasets", json=NEW_DATASET, headers={"X-API-Key": ""})
    assert r.status_code == 403


def test_real_dataset_file_matches_the_api_model():
    """Data contract: the committed pipeline output must load cleanly into the API model."""
    areas = InMemorySuburbRepository.from_csv(Settings().sample_csv).list_suburbs()
    assert len(areas) > 300
    assert len({a.code for a in areas}) == len(areas)
    assert all(a.area_sqkm > 0 and a.median_household_income > 0 for a in areas)


def test_about_credits_both_publishers_and_links_the_licence(client):
    body = client.get("/api/about").json()
    assert body["licence_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "Australian Bureau of Statistics" in body["attribution"]
    assert "Department of Transport and Planning" in body["attribution"]
    assert {s["publisher"] for s in body["sources"]} == {
        "Australian Bureau of Statistics",
        "Department of Transport and Planning (Victoria)",
    }
    assert all(s["licence_url"] == body["licence_url"] for s in body["sources"])
    assert any("kaggle.com" in s["url"] for s in body["sources"])
    assert "Kaggle" in body["attribution"]


def test_geojson_export_carries_attribution_and_licence(client):
    body = client.get("/api/suburbs/geojson").json()
    assert body["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "Australian Bureau of Statistics" in body["attribution"]


def test_api_docs_include_attribution(client):
    description = client.get("/api/openapi.json").json()["info"]["description"]
    assert "Department of Transport and Planning" in description
    assert "creativecommons.org/licenses/by/4.0" in description


def test_tag_counts_are_sorted_by_count_then_name(client):
    body = client.get("/api/datasets/tags").json()
    counts = {t["tag"]: t["count"] for t in body}
    assert counts["vic"] == 2  # GTFS and road crashes
    assert counts["geospatial"] == 2  # ASGS boundaries and OpenStreetMap
    # Ties are broken alphabetically, so "geospatial" comes before "vic".
    assert body[:2] == [{"tag": "geospatial", "count": 2}, {"tag": "vic", "count": 2}]
    assert [t["count"] for t in body] == sorted((t["count"] for t in body), reverse=True)


def test_provenance_describes_the_current_dataset(client):
    body = client.get("/api/provenance").json()
    assert body["output"]["rows"] == 5
    assert body["parameters"]["crash_years"] == [2019, 2023]
    assert body["skipped"] == [{"code": "A9", "name": "Airport", "reason": "population 12 is below 1000"}]
    crash_source = body["sources"][0]
    assert crash_source["retrieved_via"] == "Kaggle API"
    assert crash_source["version"] == 3  # source-specific fields are kept
    assert "recorded_at" in body


def test_provenance_history_summarises_versions(client):
    body = client.get("/api/provenance/history").json()
    assert len(body) == 1
    assert body[0]["rows"] == 5
    assert body[0]["skipped_count"] == 1


def test_provenance_404_without_manifest(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    from .conftest import FIXTURE_CSV

    settings = Settings(data_backend="memory", sample_csv=FIXTURE_CSV, manifest_path=tmp_path / "none.json")
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/provenance").status_code == 404
        assert c.get("/api/health").status_code == 200  # a missing manifest never stops the API


def test_committed_manifest_matches_the_committed_csv():
    """Data contract: the manifest must describe exactly the CSV in the repository."""
    import hashlib
    import json

    settings = Settings()
    manifest = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
    assert manifest["output"]["sha256"] == hashlib.sha256(settings.sample_csv.read_bytes()).hexdigest()
    assert manifest["output"]["rows"] == len(
        InMemorySuburbRepository.from_csv(settings.sample_csv).list_suburbs()
    )
