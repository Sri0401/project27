from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Suburb(BaseModel):
    """Indicators for one ABS Statistical Area Level 2 (SA2), roughly one suburb."""

    code: str = Field(description="ABS SA2 code (2021)")
    name: str
    state: str
    latitude: float
    longitude: float
    area_sqkm: float
    population: int
    median_age: float
    median_weekly_rent: int = Field(description="AUD per week (Census 2021)")
    median_household_income: int = Field(description="AUD per week (Census 2021)")
    green_space_pct: float = Field(description="Share of land in Parkland mesh blocks")
    pt_stops: int = Field(description="Public transport boarding points inside the area")
    road_crashes_per_year: float = Field(description="Average injury crashes per year, 2019-2023")
    reference_year: int


class ScoredSuburb(Suburb):
    population_density: float = Field(description="People per km2")
    pt_stops_per_sqkm: float
    crashes_per_1000_residents: float = Field(description="Injury crashes per year per 1,000 residents")
    rent_to_income_pct: float = Field(
        description="Median weekly rent as a % of median weekly household income"
    )
    liveability_score: float = Field(
        description="Composite percentile score from 0 (lowest) to 100 (highest)"
    )


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


class TagCount(BaseModel):
    tag: str
    count: int


# --- Provenance: how a dataset version was built (written by the pipeline's manifest) -----------


class ProvenanceOutput(BaseModel):
    file: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: int
    columns: list[str]


class ProvenanceSource(BaseModel):
    model_config = {"extra": "allow"}  # sources carry different fields (version, checksum, ...)

    name: str
    publisher: str
    url: str
    retrieved_via: str
    licence: str
    records_used: int | None = None


class SkippedArea(BaseModel):
    code: str
    name: str
    reason: str


class DatasetVersion(BaseModel):
    dataset: str
    generated_at: datetime
    pipeline_version: str
    output: ProvenanceOutput
    parameters: dict[str, Any]
    sources: list[ProvenanceSource]
    licence: dict[str, str]
    skipped: list[SkippedArea]
    recorded_at: datetime = Field(description="When the API first stored this version")


class DatasetVersionSummary(BaseModel):
    dataset: str
    generated_at: datetime
    pipeline_version: str
    rows: int
    sha256: str
    skipped_count: int


class DataSource(BaseModel):
    publisher: str
    dataset: str
    url: str
    licence: str
    licence_url: str


class About(BaseModel):
    attribution: str
    licence: str
    licence_url: str
    sources: list[DataSource]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    backend: str
    checks: dict[str, bool]
