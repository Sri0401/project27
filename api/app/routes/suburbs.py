from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..attribution import ATTRIBUTION, LICENCE_URL
from ..dependencies import get_suburb_repo
from ..models import IngestionRun, ScoredSuburb, SummaryResponse
from ..repositories import SuburbRepository
from ..scoring import score, summarise

router = APIRouter(tags=["suburbs"])

SortField = Literal[
    "liveability_score",
    "name",
    "population",
    "population_density",
    "median_weekly_rent",
    "rent_to_income_pct",
    "green_space_pct",
    "pt_stops_per_sqkm",
    "crashes_per_1000_residents",
]


def _scored(repo: SuburbRepository) -> list[ScoredSuburb]:
    # Score against every area, not just the filtered ones, so a score does not change with the filter.
    return score(repo.list_suburbs())


@router.get("/suburbs", response_model=list[ScoredSuburb])
def list_suburbs(
    q: str | None = Query(default=None, max_length=50, description="Case-insensitive name search"),
    state: str | None = Query(default=None, max_length=8, description="e.g. VIC"),
    min_green_space: float | None = Query(default=None, ge=0, le=100, description="Minimum green space %"),
    max_rent: int | None = Query(default=None, ge=0, description="Max median weekly rent (AUD)"),
    sort_by: SortField = "liveability_score",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=50, ge=1, le=1000),
    repo: SuburbRepository = Depends(get_suburb_repo),
) -> list[ScoredSuburb]:
    needle = q.lower() if q else None
    results = [
        s
        for s in _scored(repo)
        if (needle is None or needle in s.name.lower())
        and (state is None or s.state == state.upper())
        and (min_green_space is None or s.green_space_pct >= min_green_space)
        and (max_rent is None or s.median_weekly_rent <= max_rent)
    ]
    results.sort(key=lambda s: getattr(s, sort_by), reverse=order == "desc")
    return results[:limit]


@router.get("/suburbs/geojson", summary="All areas as a GeoJSON FeatureCollection")
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
    # Extra top-level members are allowed by GeoJSON (RFC 7946, section 6.1), so the credit and
    # licence link travel with the file when it is downloaded or opened in a GIS tool.
    return {
        "type": "FeatureCollection",
        "attribution": ATTRIBUTION,
        "license": LICENCE_URL,
        "features": features,
    }


@router.get("/suburbs/{code}", response_model=ScoredSuburb)
def get_suburb(code: str, repo: SuburbRepository = Depends(get_suburb_repo)) -> ScoredSuburb:
    for s in _scored(repo):
        if s.code.lower() == code.lower():
            return s
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Area '{code}' not found")


@router.get("/indicators/summary", response_model=SummaryResponse)
def indicator_summary(repo: SuburbRepository = Depends(get_suburb_repo)) -> SummaryResponse:
    scored = _scored(repo)
    return SummaryResponse(
        suburb_count=len(scored),
        total_population=sum(s.population for s in scored),
        indicators=summarise(scored),
    )


@router.get("/ingestion/latest", response_model=IngestionRun)
def latest_ingestion(repo: SuburbRepository = Depends(get_suburb_repo)) -> IngestionRun:
    run = repo.latest_ingestion()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No ingestion has run yet")
    return run
