import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient

from .attribution import ATTRIBUTION, LICENCE_NAME, LICENCE_URL, SOURCES
from .config import Settings
from .dependencies import get_dataset_repo, get_settings, get_suburb_repo
from .models import About, Health
from .repositories import (
    DatasetRepository,
    InMemoryDatasetRepository,
    InMemoryProvenanceRepository,
    InMemorySuburbRepository,
    MongoDatasetRepository,
    MongoProvenanceRepository,
    PostgresSuburbRepository,
    ProvenanceRepository,
    SuburbRepository,
)
from .routes import datasets, provenance, suburbs
from .seed import seed_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@dataclass
class Stores:
    suburbs: SuburbRepository
    datasets: DatasetRepository
    provenance: ProvenanceRepository
    close: Callable[[], None]


def build_stores(settings: Settings) -> Stores:
    if settings.data_backend == "memory":
        return Stores(
            suburbs=InMemorySuburbRepository.from_csv(settings.sample_csv),
            datasets=InMemoryDatasetRepository(),
            provenance=InMemoryProvenanceRepository(),
            close=lambda: None,
        )
    if settings.data_backend == "postgres":
        suburb_repo = PostgresSuburbRepository(settings.database_url)
        # One client (and connection pool) is shared by both MongoDB collections.
        mongo = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=3000, tz_aware=True)
        db = mongo[settings.mongo_db]

        def close() -> None:
            suburb_repo.close()
            mongo.close()

        return Stores(suburb_repo, MongoDatasetRepository(db), MongoProvenanceRepository(db), close)
    raise ValueError(f"Unknown DATA_BACKEND '{settings.data_backend}' (use 'postgres' or 'memory')")


def record_manifest(repo: ProvenanceRepository, path: Path) -> None:
    """Store the pipeline's provenance manifest. Failures are logged, never fatal."""
    if not path.is_file():
        log.warning("No provenance manifest at %s", path)
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if repo.record(manifest):
            log.info("Recorded new dataset version %s", manifest["output"]["sha256"][:12])
    except Exception:
        log.exception("Could not record the provenance manifest")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        stores = build_stores(settings)
        app.state.suburb_repo = stores.suburbs
        app.state.dataset_repo = stores.datasets
        app.state.provenance_repo = stores.provenance
        seed_datasets(stores.datasets)
        record_manifest(stores.provenance, settings.manifest_path)
        yield
        stores.close()

    app = FastAPI(
        title="UrbanPulse API",
        version="1.0.0",
        description=(
            "Liveability indicators for Greater Melbourne SA2 areas and an open-data catalogue for "
            f"urban research.\n\n**Data attribution:** {ATTRIBUTION}\n\n"
            "See `GET /api/about` for each source and its licence."
        ),
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
        )

    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=Health, tags=["ops"])
    def health(
        cfg: Settings = Depends(get_settings),
        suburb_repo: SuburbRepository = Depends(get_suburb_repo),
        dataset_repo: DatasetRepository = Depends(get_dataset_repo),
    ) -> JSONResponse:
        checks = {"suburb_store": suburb_repo.ping(), "dataset_store": dataset_repo.ping()}
        ok = all(checks.values())
        body = Health(
            status="ok" if ok else "degraded",
            backend=cfg.data_backend,
            version=cfg.app_version,
            checks=checks,
        )
        # 503 lets Docker health checks and load balancers notice a broken dependency.
        return JSONResponse(body.model_dump(), status_code=200 if ok else 503)

    @api.get("/about", response_model=About, tags=["ops"], summary="Data sources, licence and attribution")
    def about() -> About:
        return About(attribution=ATTRIBUTION, licence=LICENCE_NAME, licence_url=LICENCE_URL, sources=SOURCES)

    api.include_router(suburbs.router)
    api.include_router(datasets.router)
    api.include_router(provenance.router)
    app.include_router(api)

    if settings.serve_static and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")

    return app


app = create_app()
