from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_dataset_repo, require_api_key
from ..models import Dataset, DatasetIn
from ..repositories import DatasetRepository, DuplicateDatasetError

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[Dataset])
def list_datasets(
    tag: str | None = Query(default=None, max_length=40),
    repo: DatasetRepository = Depends(get_dataset_repo),
) -> list[Dataset]:
    return repo.list_datasets(tag)


@router.post(
    "",
    response_model=Dataset,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def register_dataset(dataset: DatasetIn, repo: DatasetRepository = Depends(get_dataset_repo)) -> Dataset:
    try:
        return repo.add_dataset(dataset)
    except DuplicateDatasetError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Dataset '{dataset.slug}' already exists") from None
