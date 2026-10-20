"""Data access.

The routes depend only on the two Protocols below. PostgreSQL and MongoDB back them in
production. In-memory versions back them in tests and when running without databases.
"""

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
from pymongo.errors import PyMongoError

from .models import Dataset, DatasetIn, IngestionRun, Suburb


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
    def ping(self) -> bool: ...
    def close(self) -> None: ...


# --- PostgreSQL -------------------------------------------------------------------------------

_SUBURB_COLUMNS = (
    "code, name, state, latitude, longitude, population, median_age, median_weekly_rent, "
    "walk_score, green_space_pct, pt_stops, reference_year"
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


class MongoDatasetRepository:
    """Dataset metadata varies a lot between publishers, so it lives in a document store."""

    def __init__(self, mongo_url: str, db_name: str) -> None:
        self._client: MongoClient = MongoClient(mongo_url, serverSelectionTimeoutMS=3000, tz_aware=True)
        self._collection = self._client[db_name]["datasets"]
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

    def ping(self) -> bool:
        try:
            self._client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def close(self) -> None:
        self._client.close()


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

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        pass
