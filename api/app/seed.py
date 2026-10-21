"""Open datasets added to the catalogue on first start, so a fresh install has content."""

import logging

from .models import DatasetIn
from .repositories import DatasetRepository, DuplicateDatasetError

log = logging.getLogger(__name__)

SEED_DATASETS = [
    DatasetIn(
        slug="abs-census-datapacks",
        title="ABS Census DataPacks",
        publisher="Australian Bureau of Statistics",
        licence="CC BY 4.0",
        url="https://www.abs.gov.au/census/find-census-data/datapacks",
        tags=["census", "population", "demographics"],
        description="Census tables for every geography, from mesh blocks to states.",
    ),
    DatasetIn(
        slug="abs-asgs-2021",
        title="ABS Australian Statistical Geography Standard (ASGS) Edition 3",
        publisher="Australian Bureau of Statistics",
        licence="CC BY 4.0",
        url="https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3",
        tags=["boundaries", "geospatial", "sa2", "mesh-blocks"],
        description="Official boundaries from mesh blocks to states, with land use for each mesh block.",
    ),
    DatasetIn(
        slug="aurin-data-provider",
        title="AURIN Data Provider",
        publisher="AURIN",
        licence="Various",
        url="https://data.aurin.org.au/",
        tags=["urban", "catalogue"],
        description="Catalogue of curated urban and regional research datasets.",
    ),
    DatasetIn(
        slug="ptv-gtfs-timetable",
        title="Victorian GTFS Schedule (public transport timetable)",
        publisher="Department of Transport and Planning (VIC)",
        licence="CC BY 4.0",
        url="https://opendata.transport.vic.gov.au/dataset/gtfs-schedule",
        tags=["transport", "gtfs", "vic"],
        description="Stops, routes and timetables for Victorian public transport.",
    ),
    DatasetIn(
        slug="vic-road-crashes-kaggle",
        title="Road crashes, Victoria (Kaggle)",
        publisher="Department of Transport and Planning (VIC)",
        licence="CC BY 4.0",
        url="https://www.kaggle.com/datasets/nationaldigitalau/vic-road-crashes",
        tags=["road-safety", "crashes", "vic", "kaggle"],
        description="Injury crashes reported to Victoria Police since 2012, with coordinates and ABS areas.",
    ),
    DatasetIn(
        slug="osm-australia",
        title="OpenStreetMap Australia extract",
        publisher="OpenStreetMap contributors",
        licence="ODbL 1.0",
        url="https://download.geofabrik.de/australia-oceania/australia.html",
        tags=["osm", "geospatial", "parks", "roads"],
        description="Roads, paths, parks and amenities, useful for walkability and green space.",
    ),
]


def seed_datasets(repo: DatasetRepository) -> None:
    try:
        if repo.list_datasets():
            return
        for dataset in SEED_DATASETS:
            try:
                repo.add_dataset(dataset)
            except DuplicateDatasetError:
                pass  # Another API replica seeded it at the same moment.
        log.info("Seeded %d datasets", len(SEED_DATASETS))
    except Exception:
        # Seeding is a convenience. If MongoDB is down, the API still starts and /health shows it.
        log.exception("Could not seed the dataset catalogue")
