from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_API_KEY = "test-key"


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(data_backend="memory", api_key=TEST_API_KEY)
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def client_without_key() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(data_backend="memory"))) as c:
        yield c
