"""Data access.

The routes depend only on the Protocols below. PostgreSQL and MongoDB back them in production.
In-memory versions back them in tests and when running without databases.
"""

import csv
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
from pymongo.errors import PyMongoError

from .models import Dataset, DatasetIn, DatasetVersion, DatasetVersionSummary, IngestionRun, Suburb, TagCount


class DuplicateDatasetError(Exception):
    pass


class SuburbRepository(Protocol):
    def list_suburbs(self) -> list[Suburb]: ...
    def latest_ingestion(self) -> IngestionRun | None: ...
    def ping(self) -> bool: ...
    def close(self) -> None: ...


class DatasetRepository(Protocol):
    def list_datasets(self, tag: str | None = None) -> list[Dataset]: ...
    def add_dataset(self, dataset: DatasetIn) -> Dataset: ...
    def tag_counts(self) -> list[TagCount]: ...
    def ping(self) -> bool: ...


class ProvenanceRepository(Protocol):
    def record(self, manifest: dict[str, Any]) -> bool: ...
    def latest(self) -> DatasetVersion | None: ...
    def history(self, limit: int = 20) -> list[DatasetVersionSummary]: ...


# --- PostgreSQL -------------------------------------------------------------------------------

_SUBURB_COLUMNS = (
    "code, name, state, latitude, longitude, area_sqkm, population, median_age, median_weekly_rent, "
    "median_household_income, green_space_pct, pt_stops, road_crashes_per_year, reference_year"
)


class PostgresSuburbRepository:
    def __init__(self, database_url: str) -> None:
        # open=False plus an explicit open() lets the API start even if the database is briefly down.
        self._pool = ConnectionPool(
            database_url, min_size=1, max_size=5, open=False, kwargs={"row_factory": dict_row}
        )
        self._pool.open(wait=False)

    def list_suburbs(self) -> list[Suburb]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"SELECT {_SUBURB_COLUMNS} FROM suburb_indicators ORDER BY name"  # noqa: S608
            ).fetchall()
        return [Suburb.model_validate(row) for row in rows]

    def latest_ingestion(self) -> IngestionRun | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT source, rows_loaded, rows_rejected, started_at, finished_at "
                "FROM ingestion_runs ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
        return IngestionRun.model_validate(row) if row else None

    def ping(self) -> bool:
        try:
            with self._pool.connection(timeout=2) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._pool.close()


# --- MongoDB ----------------------------------------------------------------------------------
# Both collections hold documents whose shape varies: publishers describe datasets differently, and
# a provenance manifest nests sources and excluded areas that change from one build to the next.


class MongoDatasetRepository:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._collection = db["datasets"]
        self._indexes_ready = False

    def _ensure_indexes(self) -> None:
        if not self._indexes_ready:
            self._collection.create_index([("slug", ASCENDING)], unique=True)
            self._collection.create_index([("tags", ASCENDING)])
            self._indexes_ready = True

    def list_datasets(self, tag: str | None = None) -> list[Dataset]:
        query = {"tags": tag} if tag else {}
        docs = self._collection.find(query, {"_id": 0}).sort("title", ASCENDING)
        return [Dataset.model_validate(doc) for doc in docs]

    def add_dataset(self, dataset: DatasetIn) -> Dataset:
        self._ensure_indexes()
        stored = Dataset(**dataset.model_dump(), registered_at=datetime.now(UTC))
        try:
            self._collection.insert_one(stored.model_dump())
        except MongoDuplicateKeyError as e:
            raise DuplicateDatasetError(dataset.slug) from e
        return stored

    def tag_counts(self) -> list[TagCount]:
        """Count datasets per tag with an aggregation pipeline, so the database does the work."""
        pipeline = [
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": DESCENDING, "_id": ASCENDING}},
            {"$project": {"_id": 0, "tag": "$_id", "count": 1}},
        ]
        return [TagCount.model_validate(doc) for doc in self._collection.aggregate(pipeline)]

    def ping(self) -> bool:
        try:
            self._db.client.admin.command("ping")
            return True
        except PyMongoError:
            return False


class MongoProvenanceRepository:
    """Stores one document per dataset version, keyed by the checksum of the CSV it describes."""

    def __init__(self, db: Database) -> None:
        self._collection = db["dataset_versions"]
        self._indexes_ready = False

    def _ensure_indexes(self) -> None:
        if not self._indexes_ready:
            self._collection.create_index([("output.sha256", ASCENDING)], unique=True)
            self._collection.create_index([("generated_at", DESCENDING)])
            self._indexes_ready = True

    def record(self, manifest: dict[str, Any]) -> bool:
        """Store a manifest if its dataset version is new. Returns True if it was inserted.

        An upsert keyed on the checksum makes this idempotent: every API replica can call it on
        start-up and the version is stored exactly once.
        """
        self._ensure_indexes()
        version = DatasetVersion(**manifest, recorded_at=datetime.now(UTC))
        result = self._collection.update_one(
            {"output.sha256": version.output.sha256},
            {"$setOnInsert": version.model_dump(mode="json")},
            upsert=True,
        )
        return result.upserted_id is not None

    def latest(self) -> DatasetVersion | None:
        doc = self._collection.find_one({}, {"_id": 0}, sort=[("generated_at", DESCENDING)])
        return DatasetVersion.model_validate(doc) if doc else None

    def history(self, limit: int = 20) -> list[DatasetVersionSummary]:
        # $project returns only summary fields and counts excluded areas in the database,
        # instead of sending every source and excluded area to the API.
        pipeline = [
            {"$sort": {"generated_at": DESCENDING}},
            {"$limit": limit},
            {
                "$project": {
                    "_id": 0,
                    "dataset": 1,
                    "generated_at": 1,
                    "pipeline_version": 1,
                    "rows": "$output.rows",
                    "sha256": "$output.sha256",
                    "skipped_count": {"$size": "$skipped"},
                }
            },
        ]
        return [DatasetVersionSummary.model_validate(doc) for doc in self._collection.aggregate(pipeline)]


# --- In-memory --------------------------------------------------------------------------------


class InMemorySuburbRepository:
    def __init__(self, suburbs: list[Suburb]) -> None:
        self._suburbs = sorted(suburbs, key=lambda s: s.name)
        self._loaded_at = datetime.now(UTC)
        self._source = "in-memory"

    @classmethod
    def from_csv(cls, path: Path) -> "InMemorySuburbRepository":
        with path.open(newline="", encoding="utf-8-sig") as f:
            repo = cls([Suburb.model_validate(row) for row in csv.DictReader(f)])
        repo._source = path.name
        return repo

    def list_suburbs(self) -> list[Suburb]:
        return list(self._suburbs)

    def latest_ingestion(self) -> IngestionRun | None:
        return IngestionRun(
            source=self._source,
            rows_loaded=len(self._suburbs),
            rows_rejected=0,
            started_at=self._loaded_at,
            finished_at=self._loaded_at,
        )

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        pass


class InMemoryDatasetRepository:
    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}

    def list_datasets(self, tag: str | None = None) -> list[Dataset]:
        items = sorted(self._datasets.values(), key=lambda d: d.title)
        return [d for d in items if tag is None or tag in d.tags]

    def add_dataset(self, dataset: DatasetIn) -> Dataset:
        if dataset.slug in self._datasets:
            raise DuplicateDatasetError(dataset.slug)
        stored = Dataset(**dataset.model_dump(), registered_at=datetime.now(UTC))
        self._datasets[dataset.slug] = stored
        return stored

    def tag_counts(self) -> list[TagCount]:
        counts = Counter(tag for d in self._datasets.values() for tag in d.tags)
        return [TagCount(tag=t, count=c) for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    def ping(self) -> bool:
        return True


class InMemoryProvenanceRepository:
    def __init__(self) -> None:
        self._versions: dict[str, DatasetVersion] = {}

    def record(self, manifest: dict[str, Any]) -> bool:
        version = DatasetVersion(**manifest, recorded_at=datetime.now(UTC))
        if version.output.sha256 in self._versions:
            return False
        self._versions[version.output.sha256] = version
        return True

    def latest(self) -> DatasetVersion | None:
        return max(self._versions.values(), key=lambda v: v.generated_at, default=None)

    def history(self, limit: int = 20) -> list[DatasetVersionSummary]:
        ordered = sorted(self._versions.values(), key=lambda v: v.generated_at, reverse=True)[:limit]
        return [
            DatasetVersionSummary(
                dataset=v.dataset,
                generated_at=v.generated_at,
                pipeline_version=v.pipeline_version,
                rows=v.output.rows,
                sha256=v.output.sha256,
                skipped_count=len(v.skipped),
            )
            for v in ordered
        ]
