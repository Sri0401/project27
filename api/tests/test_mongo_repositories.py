"""MongoDB repositories, tested against mongomock (an in-memory MongoDB) so no server is needed.

CI's end-to-end job also runs the same code against a real MongoDB 7 container.
"""

import json
from pathlib import Path

import mongomock
import pytest

from app.models import DatasetIn
from app.repositories import DuplicateDatasetError, MongoDatasetRepository, MongoProvenanceRepository

MANIFEST = json.loads((Path(__file__).parent / "fixtures" / "areas.manifest.json").read_text())


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["urbanpulse_test"]


def dataset(slug: str, tags: list[str]) -> DatasetIn:
    return DatasetIn(
        slug=slug, title=slug.title(), publisher="Test", licence="CC0", url="https://x.org", tags=tags
    )


def test_dataset_catalogue_round_trip_and_unique_slug(db):
    repo = MongoDatasetRepository(db)
    repo.add_dataset(dataset("transport-a", ["transport", "vic"]))
    repo.add_dataset(dataset("census-b", ["census"]))

    assert [d.slug for d in repo.list_datasets()] == ["census-b", "transport-a"]  # sorted by title
    assert [d.slug for d in repo.list_datasets("vic")] == ["transport-a"]
    with pytest.raises(DuplicateDatasetError):
        repo.add_dataset(dataset("census-b", []))


def test_tag_counts_aggregation(db):
    repo = MongoDatasetRepository(db)
    repo.add_dataset(dataset("one", ["vic", "transport"]))
    repo.add_dataset(dataset("two", ["vic", "census"]))
    repo.add_dataset(dataset("three", ["census", "vic"]))

    assert [(t.tag, t.count) for t in repo.tag_counts()] == [("vic", 3), ("census", 2), ("transport", 1)]


def test_provenance_record_is_idempotent(db):
    repo = MongoProvenanceRepository(db)
    assert repo.record(MANIFEST) is True
    assert repo.record(MANIFEST) is False  # same CSV checksum, so not stored twice
    assert db["dataset_versions"].count_documents({}) == 1


def test_provenance_latest_and_history(db):
    repo = MongoProvenanceRepository(db)
    older = {
        **MANIFEST,
        "generated_at": "2026-09-01T00:00:00+00:00",
        "output": {**MANIFEST["output"], "sha256": "a" * 64},
    }
    repo.record(older)
    repo.record(MANIFEST)

    latest = repo.latest()
    assert latest is not None and latest.output.sha256 == MANIFEST["output"]["sha256"]
    assert latest.sources[0].model_extra["version"] == 3

    history = repo.history()
    assert [h.sha256 for h in history] == [MANIFEST["output"]["sha256"], "a" * 64]
    assert history[0].skipped_count == 1
    assert len(repo.history(limit=1)) == 1
