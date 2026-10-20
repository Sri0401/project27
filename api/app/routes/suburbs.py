from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_suburb_repo
from ..models import IngestionRun, ScoredSuburb, SummaryResponse
from ..repositories import SuburbRepository
from ..scoring import liveability_scores, summarise

router = APIRouter(tags=["suburbs"])

SortField = Literal[
    "liveability_score", "name", "population", "median_weekly_rent", "walk_score", "green_space_pct"
]


def _scored(repo: SuburbRepository) -> list[ScoredSuburb]:
    # Score against every suburb, not just the filtered ones, so a score does not change with the filter.
    suburbs = repo.list_suburbs()
    scores = liveability_scores(suburbs)
    return [ScoredSuburb(**s.model_dump(), liveability_score=scores[s.code]) for s in suburbs]


@router.get("/suburbs", response_model=list[ScoredSuburb])
def list_suburbs(
    state: str | None = Query(default=None, max_length=8, description="e.g. VIC"),
    min_walk_score: int | None = Query(default=None, ge=0, le=100),
    max_rent: int | None = Query(default=None, ge=0, description="Max median weekly rent (AUD)"),
    sort_by: SortField = "liveability_score",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=50, ge=1, le=500),
    repo: SuburbRepository = Depends(get_suburb_repo),
) -> list[ScoredSuburb]:
    results = [
        s
        for s in _scored(repo)
        if (state is None or s.state == state.upper())
        and (min_walk_score is None or s.walk_score >= min_walk_score)
        and (max_rent is None or s.median_weekly_rent <= max_rent)
    ]
    results.sort(key=lambda s: getattr(s, sort_by), reverse=order == "desc")
    return results[:limit]


@router.get("/suburbs/geojson", summary="All suburbs as a GeoJSON FeatureCollection")
def suburbs_geojson(repo: SuburbRepository = Depends(get_suburb_repo)) -> dict[str, Any]:
    features = [
        {
            "type": "Feature",
            "id": s.code,
            # GeoJSON order is [longitude, latitude].
            "geometry": {"type": "Point", "coordinates": [s.longitude, s.latitude]},
            "properties": s.model_dump(exclude={"latitude", "longitude"}),
        }
        for s in _scored(repo)
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/suburbs/{code}", response_model=ScoredSuburb)
def get_suburb(code: str, repo: SuburbRepository = Depends(get_suburb_repo)) -> ScoredSuburb:
    for s in _scored(repo):
        if s.code.lower() == code.lower():
            return s
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Suburb '{code}' not found")


@router.get("/indicators/summary", response_model=SummaryResponse)
def indicator_summary(repo: SuburbRepository = Depends(get_suburb_repo)) -> SummaryResponse:
    suburbs = repo.list_suburbs()
    return SummaryResponse(
        suburb_count=len(suburbs),
        total_population=sum(s.population for s in suburbs),
        indicators=summarise(suburbs),
    )


@router.get("/ingestion/latest", response_model=IngestionRun)
def latest_ingestion(repo: SuburbRepository = Depends(get_suburb_repo)) -> IngestionRun:
    run = repo.latest_ingestion()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No ingestion has run yet")
    return run
