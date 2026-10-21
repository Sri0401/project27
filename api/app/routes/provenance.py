from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_provenance_repo
from ..models import DatasetVersion, DatasetVersionSummary
from ..repositories import ProvenanceRepository

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.get("", response_model=DatasetVersion, summary="How the current dataset was built")
def latest_version(repo: ProvenanceRepository = Depends(get_provenance_repo)) -> DatasetVersion:
    version = repo.latest()
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No dataset version has been recorded")
    return version


@router.get("/history", response_model=list[DatasetVersionSummary], summary="Every recorded dataset version")
def version_history(
    limit: int = Query(default=20, ge=1, le=100),
    repo: ProvenanceRepository = Depends(get_provenance_repo),
) -> list[DatasetVersionSummary]:
    return repo.history(limit)
