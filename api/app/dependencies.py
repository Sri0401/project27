import secrets

from fastapi import Header, HTTPException, Request, status

from .config import Settings
from .repositories import DatasetRepository, SuburbRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_suburb_repo(request: Request) -> SuburbRepository:
    return request.app.state.suburb_repo


def get_dataset_repo(request: Request) -> DatasetRepository:
    return request.app.state.dataset_repo


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Protect write endpoints. If no key is configured, writes are switched off."""
    expected = get_settings(request).api_key
    if not expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Writes are disabled: API_KEY is not set")
    # compare_digest takes the same time whatever the input, so it does not leak the key.
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-API-Key header")
