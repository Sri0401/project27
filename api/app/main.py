import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .dependencies import get_dataset_repo, get_settings, get_suburb_repo
from .models import Health
from .repositories import (
    DatasetRepository,
    InMemoryDatasetRepository,
    InMemorySuburbRepository,
    MongoDatasetRepository,
    PostgresSuburbRepository,
    SuburbRepository,
)
from .routes import datasets, suburbs
from .seed import seed_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_repositories(settings: Settings) -> tuple[SuburbRepository, DatasetRepository]:
    if settings.data_backend == "memory":
        return InMemorySuburbRepository.from_csv(settings.sample_csv), InMemoryDatasetRepository()
    if settings.data_backend == "postgres":
        return (
            PostgresSuburbRepository(settings.database_url),
            MongoDatasetRepository(settings.mongo_url, settings.mongo_db),
        )
    raise ValueError(f"Unknown DATA_BACKEND '{settings.data_backend}' (use 'postgres' or 'memory')")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.suburb_repo, app.state.dataset_repo = build_repositories(settings)
        seed_datasets(app.state.dataset_repo)
        yield
        app.state.suburb_repo.close()
        app.state.dataset_repo.close()

    app = FastAPI(
        title="UrbanPulse API",
        version="1.0.0",
        description="Suburb liveability indicators and an open-data catalogue for urban research.",
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
        body = Health(status="ok" if ok else "degraded", backend=cfg.data_backend, checks=checks)
        # 503 lets Docker health checks and load balancers notice a broken dependency.
        return JSONResponse(body.model_dump(), status_code=200 if ok else 503)

    api.include_router(suburbs.router)
    api.include_router(datasets.router)
    app.include_router(api)

    if settings.serve_static and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")

    return app


app = create_app()
