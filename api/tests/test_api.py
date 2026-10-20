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


def test_list_suburbs_sorted_by_score_by_default(client):
    body = client.get("/api/suburbs").json()
    assert len(body) == 20
    scores = [s["liveability_score"] for s in body]
    assert scores == sorted(scores, reverse=True)


def test_filters_and_sorting(client):
    body = client.get(
        "/api/suburbs",
        params={"min_walk_score": 90, "max_rent": 550, "sort_by": "name", "order": "asc"},
    ).json()
    names = [s["name"] for s in body]
    assert names == sorted(names)
    assert all(s["walk_score"] >= 90 and s["median_weekly_rent"] <= 550 for s in body)
    assert "Docklands" not in names  # walk score 89


def test_scores_do_not_change_when_filtering(client):
    everything = {s["code"]: s["liveability_score"] for s in client.get("/api/suburbs").json()}
    filtered = client.get("/api/suburbs", params={"min_walk_score": 90}).json()
    assert all(s["liveability_score"] == everything[s["code"]] for s in filtered)


def test_invalid_query_is_rejected(client):
    assert client.get("/api/suburbs", params={"min_walk_score": 101}).status_code == 422
    assert client.get("/api/suburbs", params={"sort_by": "password"}).status_code == 422


def test_get_suburb_is_case_insensitive(client):
    r = client.get("/api/suburbs/mel03")
    assert r.status_code == 200
    assert r.json()["name"] == "Fitzroy"


def test_unknown_suburb_returns_404(client):
    assert client.get("/api/suburbs/NOPE").status_code == 404


def test_geojson(client):
    body = client.get("/api/suburbs/geojson").json()
    assert body["type"] == "FeatureCollection"
    cbd = next(f for f in body["features"] if f["id"] == "MEL01")
    assert cbd["geometry"] == {"type": "Point", "coordinates": [144.9631, -37.8136]}
    assert "liveability_score" in cbd["properties"]


def test_indicator_summary(client):
    body = client.get("/api/indicators/summary").json()
    assert body["suburb_count"] == 20
    walk = next(i for i in body["indicators"] if i["indicator"] == "walk_score")
    assert walk["min"] == 35 and walk["max"] == 98


def test_latest_ingestion(client):
    body = client.get("/api/ingestion/latest").json()
    assert body["source"] == "suburbs_sample.csv"
    assert body["rows_loaded"] == 20


def test_seeded_datasets_and_tag_filter(client):
    assert len(client.get("/api/datasets").json()) == 4
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
