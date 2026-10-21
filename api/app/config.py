"""Settings read from environment variables, so the same image runs locally and in the cloud."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # "postgres" uses PostgreSQL + MongoDB. "memory" loads the dataset CSV, so no databases are needed.
    data_backend: str = "postgres"
    database_url: str = "postgresql://urbanpulse:urbanpulse@localhost:5432/urbanpulse"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "urbanpulse"
    sample_csv: Path = REPO_ROOT / "data" / "melbourne_sa2_2021.csv"
    # Provenance manifest written by the pipeline. It is recorded in the provenance store on start-up.
    manifest_path: Path = REPO_ROOT / "data" / "melbourne_sa2_2021.manifest.json"
    # Writes need this key in the X-API-Key header. If it is empty, writes are disabled.
    api_key: str = ""
    cors_origins: tuple[str, ...] = ()
    # Serve the web/ folder from the API. Only useful when running without Nginx.
    serve_static: bool = False
    static_dir: Path = REPO_ROOT / "web"

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            data_backend=os.getenv("DATA_BACKEND", defaults.data_backend).lower(),
            database_url=os.getenv("DATABASE_URL", defaults.database_url),
            mongo_url=os.getenv("MONGO_URL", defaults.mongo_url),
            mongo_db=os.getenv("MONGO_DB", defaults.mongo_db),
            sample_csv=Path(os.getenv("SAMPLE_CSV", str(defaults.sample_csv))),
            manifest_path=Path(os.getenv("MANIFEST_PATH", str(defaults.manifest_path))),
            api_key=os.getenv("API_KEY", ""),
            cors_origins=tuple(o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()),
            serve_static=os.getenv("SERVE_STATIC", "false").lower() == "true",
            static_dir=Path(os.getenv("STATIC_DIR", str(defaults.static_dir))),
        )
