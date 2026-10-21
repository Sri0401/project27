"""Data attribution required by the CC BY 4.0 licence of the source datasets.

This is the single source of truth for the API docs, the /api/about endpoint and the GeoJSON
export, so the credit and licence link go wherever the data goes.
"""

LICENCE_NAME = "CC BY 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"

# Wording follows the ABS DataPack licence file: "Based on ABS data" for derived material, the
# permission acknowledgement, title, publication and access date, and no ABS credit for our own figures.
ATTRIBUTION = (
    "Based on ABS data: Australian Bureau of Statistics, 2021 Census of Population and Housing, "
    "General Community Profile DataPack (Release 2, files dated 16 January 2023), SA2, Victoria; "
    "and Australian Statistical Geography Standard (ASGS) Edition 3, July 2021 - June 2026; both "
    "accessed 20 October 2026 (https://www.abs.gov.au). ABS data used with permission from the "
    "Australian Bureau of Statistics. Also based on Department of Transport and Planning "
    "(Victoria) data: GTFS Schedule, accessed 20 October 2026; and Victoria Road Crash Data, "
    "accessed 12 October 2026, obtained via the Kaggle dataset "
    f"nationaldigitalau/vic-road-crashes. All licensed under CC BY 4.0 ({LICENCE_URL}). Changes "
    "were made: data joined, aggregated to SA2 and filtered. Derived indicators and the "
    "liveability score are UrbanPulse calculations, not ABS or DTP statistics. Not endorsed by "
    "the ABS or DTP."
)

SOURCES = [
    {
        "publisher": "Australian Bureau of Statistics",
        "dataset": "2021 Census General Community Profile DataPack (G01, G02), SA2, Victoria",
        "url": "https://www.abs.gov.au/census/find-census-data/datapacks",
        "licence": LICENCE_NAME,
        "licence_url": LICENCE_URL,
    },
    {
        "publisher": "Australian Bureau of Statistics",
        "dataset": "Australian Statistical Geography Standard (ASGS) Ed. 3: SA2 boundaries and Mesh Blocks",
        "url": "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3",
        "licence": LICENCE_NAME,
        "licence_url": LICENCE_URL,
    },
    {
        "publisher": "Department of Transport and Planning (Victoria)",
        "dataset": "GTFS Schedule",
        "url": "https://opendata.transport.vic.gov.au/dataset/gtfs-schedule",
        "licence": LICENCE_NAME,
        "licence_url": LICENCE_URL,
    },
    {
        "publisher": "Department of Transport and Planning (Victoria)",
        "dataset": "Victoria Road Crash Data 2019-2023 (Kaggle: nationaldigitalau/vic-road-crashes v3)",
        "url": "https://www.kaggle.com/datasets/nationaldigitalau/vic-road-crashes",
        "licence": LICENCE_NAME,
        "licence_url": LICENCE_URL,
    },
]
