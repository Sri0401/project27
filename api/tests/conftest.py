from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_API_KEY = "test-key"
# A small, hand-made dataset so expected values can be worked out by hand.
FIXTURE_CSV = Path(__file__).parent / "fixtures" / "areas.csv"
FIXTURE_MANIFEST = Path(__file__).parent / "fixtures" / "areas.manifest.json"


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        data_backend="memory", sample_csv=FIXTURE_CSV, manifest_path=FIXTURE_MANIFEST, api_key=TEST_API_KEY
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def client_without_key() -> Iterator[TestClient]:
    settings = Settings(data_backend="memory", sample_csv=FIXTURE_CSV, manifest_path=FIXTURE_MANIFEST)
    with TestClient(create_app(settings)) as c:
        yield c
