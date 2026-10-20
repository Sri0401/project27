from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Suburb(BaseModel):
    code: str
    name: str
    state: str
    latitude: float
    longitude: float
    population: int
    median_age: float
    median_weekly_rent: int
    walk_score: int
    green_space_pct: float
    pt_stops: int
    reference_year: int


class ScoredSuburb(Suburb):
    liveability_score: float = Field(description="Composite score from 0 (lowest) to 100 (highest)")


class IndicatorSummary(BaseModel):
    indicator: str
    min: float
    max: float
    mean: float
    median: float


class SummaryResponse(BaseModel):
    suburb_count: int
    total_population: int
    indicators: list[IndicatorSummary]


class IngestionRun(BaseModel):
    source: str
    rows_loaded: int
    rows_rejected: int
    started_at: datetime
    finished_at: datetime


class DatasetIn(BaseModel):
    """Metadata for an open dataset that researchers can use."""

    slug: str = Field(pattern=r"^[a-z0-9-]{3,64}$", examples=["abs-census-2021-g01"])
    title: str = Field(min_length=3, max_length=200)
    publisher: str = Field(min_length=2, max_length=120)
    licence: str = Field(min_length=2, max_length=60, examples=["CC BY 4.0"])
    url: str = Field(pattern=r"^https?://\S+$", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)
    description: str = Field(default="", max_length=2000)


class Dataset(DatasetIn):
    registered_at: datetime


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    backend: str
    checks: dict[str, bool]
