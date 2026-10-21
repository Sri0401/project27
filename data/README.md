# Data

`melbourne_sa2_2021.csv` holds liveability indicators for **354 Statistical Areas Level 2 (SA2s) in Greater Melbourne**. SA2s are the ABS's standard small areas for research statistics. Each one represents a community of roughly 3,000 to 25,000 people, and in cities most line up closely with suburbs.

The file is produced by [`pipeline/build_dataset.py`](../pipeline/build_dataset.py) from official open data. Next to it, [`melbourne_sa2_2021.manifest.json`](melbourne_sa2_2021.manifest.json) records exactly how it was built: each source with its URL, version, file checksum, licence and number of records used, the parameters, the CSV's SHA-256, and every excluded area with its reason. The API stores each manifest in MongoDB and serves it at `/api/provenance`. To rebuild it:

```bash
cd pipeline
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python build_dataset.py        # about 300 MB of downloads the first time, then cached
```

## Sources and licences

| Source | Used for | Licence |
|---|---|---|
| [ABS 2021 Census General Community Profile DataPack](https://www.abs.gov.au/census/find-census-data/datapacks), SA2, Victoria (tables G01 and G02) | Population, median age, median weekly rent, median weekly household income | CC BY 4.0 |
| [ABS ASGS Edition 3](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3), SA2 boundaries ([ArcGIS REST service](https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SA2/MapServer)) | Area name, area in km², map point, stop counting | CC BY 4.0 |
| ABS ASGS Edition 3, Mesh Blocks ([ArcGIS REST service](https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/MB/MapServer)) | Green space: share of land in *Parkland* mesh blocks | CC BY 4.0 |
| [Victorian Department of Transport and Planning, GTFS Schedule](https://opendata.transport.vic.gov.au/dataset/gtfs-schedule) | Public transport stops (train, tram, bus, coach) | CC BY 4.0 |
| Victorian Department of Transport and Planning, [Victoria Road Crash Data](https://discover.data.vic.gov.au/dataset/victoria-road-crash-data), obtained from **Kaggle**: [nationaldigitalau/vic-road-crashes](https://www.kaggle.com/datasets/nationaldigitalau/vic-road-crashes), version 3 (12 October 2026) | Injury road crashes per area, 2019 to 2023 | CC BY 4.0 |

### What the licence allows

CC BY 4.0 lets **anyone** copy, share and adapt the data, **including for commercial purposes**, as long as they:

1. **Credit the source.** Name the ABS and the Department of Transport and Planning. For changed ABS data, the ABS asks for "Based on ABS data" plus "ABS data used with permission from the Australian Bureau of Statistics".
2. **Link to the licence**: https://creativecommons.org/licenses/by/4.0/
3. **Say if changes were made.** This file is *derived*: it joins, aggregates and filters the source data, so it says so.
4. **Don't suggest endorsement.** UrbanPulse is not affiliated with or endorsed by the ABS or DTP.

These were checked against the ABS [copyright page](https://www.abs.gov.au/website-privacy-copyright-and-disclaimer) (all ABS website material is CC BY 4.0), the copyright notice on the ABS ArcGIS services, and the licence field (`CC-BY-4.0`) in the [DTP open data portal](https://opendata.transport.vic.gov.au/dataset/gtfs-schedule) metadata. The ABS licence excludes logos, Census branding and unit-record microdata. This project uses none of them, only published aggregate tables and boundaries.

**Attribution used in this project** (dashboard footer, API, GeoJSON export, README and [NOTICE.md](../NOTICE.md)):

> Based on ABS data: Australian Bureau of Statistics, 2021 Census of Population and Housing, General Community Profile DataPack (Release 2, files dated 16 January 2023), SA2, Victoria; and Australian Statistical Geography Standard (ASGS) Edition 3, July 2021 - June 2026; both accessed 20 October 2026 (https://www.abs.gov.au). ABS data used with permission from the Australian Bureau of Statistics. Also based on Department of Transport and Planning (Victoria) data: GTFS Schedule, accessed 20 October 2026; and Victoria Road Crash Data (https://discover.data.vic.gov.au/dataset/victoria-road-crash-data), accessed 12 October 2026, serialised and versioned by National Digital at publicdata.au (https://publicdata.au/d/vic-road-crashes/v/2026-10-12/), which added ABS area codes to each crash, and obtained via the Kaggle dataset nationaldigitalau/vic-road-crashes. All licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes were made: data joined, aggregated to SA2 and filtered. Derived indicators and the liveability score are UrbanPulse calculations, not ABS or DTP statistics. Not endorsed by the ABS or DTP.

The ABS wording ("Based on ABS data", the permission acknowledgement, and title, publication and access date) follows the licence file shipped inside the Census DataPack, `Readme/CreativeCommons_Licensing_readme.txt`.

### About the Kaggle source

Kaggle hosts copies of datasets uploaded by its users, so its licence label is only as reliable as the uploader. This copy was chosen because it states its licence (CC BY 4.0), names the original publisher, gives the publisher's requested attribution text, and adds ABS area codes to each crash. The pipeline pins version 3 so rebuilds are reproducible. Public Kaggle datasets download without an account. Other Kaggle copies of the same data were rejected: one has no location columns, and others are labelled "CC0" or "Unknown", which conflicts with the publisher's CC BY 4.0 licence.

All values are aggregates for whole areas, so the file contains **no personal information**.

### Size

| File | Size |
|---|---|
| `melbourne_sa2_2021.csv` (354 rows × 14 columns) | about 33 KB (about 14 KB gzipped) |
| Source downloads, cached in `pipeline/.cache/` and not committed | Census DataPack 12 MB, GTFS bundle 255 MB, Kaggle crash data 61 MB |
| Live ABS API responses (boundaries + land use) | about 0.5 MB, not stored |

## Columns

| Column | Meaning | Source |
|---|---|---|
| `code` | ABS SA2 code (2021), for example `206071142` | ASGS |
| `name` | SA2 name, for example `Fitzroy` | ASGS |
| `state` | Always `VIC` | — |
| `latitude`, `longitude` | A point guaranteed to be inside the area (not the centroid, which can fall outside an irregular shape) | Computed from the ASGS boundary |
| `area_sqkm` | Area in km² (Albers equal-area projection) | ASGS |
| `population` | Usual resident population (`Tot_P_P`) | Census G01 |
| `median_age` | Median age of residents | Census G02 |
| `median_weekly_rent` | Median weekly rent, AUD | Census G02 |
| `median_household_income` | Median total weekly household income, AUD | Census G02 |
| `green_space_pct` | Parkland mesh-block area as a % of land area (water excluded) | ASGS Mesh Blocks |
| `pt_stops` | Unique public transport boarding points inside the area | GTFS |
| `road_crashes_per_year` | Average injury crashes per year in the area, 2019 to 2023 | Road Crash Data (Kaggle) |
| `reference_year` | 2021, the Census year | — |

## Method notes and limitations

- **Excluded areas**: 7 of the 361 Greater Melbourne SA2s are left out because their population is below 1,000: three airports, Flemington Racecourse, the Royal Botanic Gardens, Braeside and West Melbourne Industrial. Each one and its reason is listed in the manifest and on the dashboard.
- **Different dates**: Census figures are from August 2021. Boundaries are the 2021 edition. Stops come from the current GTFS feed (it rolls forward weekly), so a stop opened since 2021 is counted. Crashes are averaged over 2019 to 2023, five years centred on the Census, which also smooths out the 2020 lockdown dip.
- **Road crashes** are counted where they happen, not where the people involved live. Areas with major roads or many visitors, like the CBD, therefore show more crashes per resident. Only crashes where someone was injured or killed are recorded, because these are the ones reported to Victoria Police.
- **Green space** counts land the ABS classifies as Parkland. Street trees, private gardens and parks just over the area boundary aren't included.
- **Stops**: platforms are counted individually. Parent stations and entrances are skipped, and points repeated across feeds are counted once. A busy interchange therefore counts as several stops, which roughly reflects its higher service level.
- Boundaries are simplified to about 50 m before counting stops, so a stop right on a boundary may be assigned to the neighbouring area.
