# Third-party data notices

This project uses open data from the following publishers. Their data is licensed under the
[Creative Commons Attribution 4.0 International licence (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

## Australian Bureau of Statistics (ABS)

- [2021 Census General Community Profile DataPack](https://www.abs.gov.au/census/find-census-data/datapacks), tables G01 and G02, Statistical Area Level 2, Victoria
- [Australian Statistical Geography Standard (ASGS) Edition 3](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3): SA2 boundaries and Mesh Block land use, accessed through the [ABS ArcGIS REST services](https://geo.abs.gov.au/arcgis/rest/services/ASGS2021)

**Based on ABS data.** ABS data used with permission from the Australian Bureau of Statistics.
2021 Census of Population and Housing, General Community Profile DataPack (Release 2, files dated 16 January 2023), SA2, Victoria; and Australian Statistical Geography Standard (ASGS) Edition 3, July 2021 - June 2026. Both accessed 20 October 2026 from [www.abs.gov.au](https://www.abs.gov.au), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

This wording follows the licence file shipped inside the DataPack (`Readme/CreativeCommons_Licensing_readme.txt`) and the [ABS copyright statement](https://www.abs.gov.au/website-privacy-copyright-and-disclaimer). As that file requires, figures calculated by this project (derived indicators and the liveability score) are **not** attributed to the ABS.

## Department of Transport and Planning (DTP), Victoria

- [GTFS Schedule](https://opendata.transport.vic.gov.au/dataset/gtfs-schedule): public transport stops for trains, trams, buses and coaches
- [Victoria Road Crash Data](https://discover.data.vic.gov.au/dataset/victoria-road-crash-data): injury crashes reported to Victoria Police. Obtained through the Kaggle dataset [nationaldigitalau/vic-road-crashes](https://www.kaggle.com/datasets/nationaldigitalau/vic-road-crashes) (version 3, 12 October 2026), a [publicdata.au](https://publicdata.au/d/vic-road-crashes/) copy that adds ABS area codes to each crash.

Source: Department of Transport and Planning (Victoria), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). GTFS Schedule accessed 20 October 2026.

The crash data is a republication. As its licence requires, the republisher's credit and their change are kept:
*Serialised and versioned by National Digital at publicdata.au, https://publicdata.au/d/vic-road-crashes/v/2026-10-12/*. National Digital added ABS area codes (including SA2) to each crash. They state that it is an independent republication not endorsed by the publisher.
The publisher's requested credit for the crash data: *Department of Transport and Planning, Victoria, Victoria Road Crash Data, https://discover.data.vic.gov.au/dataset/victoria-road-crash-data, accessed 12 October 2026, licensed under CC BY 4.0.*

## Changes made

The file [`data/melbourne_sa2_2021.csv`](data/melbourne_sa2_2021.csv) is **derived** from the sources above. Census tables were joined on SA2 code. Mesh Block land use was aggregated to a green-space share for each SA2. Transport stops were counted inside each SA2 boundary. Injury crashes from 2019 to 2023 were counted for each SA2 and averaged per year. Areas with fewer than 1,000 residents or unpublished medians were removed. Derived indicators and the liveability score are this project's own calculations. The full method is in [`data/README.md`](data/README.md).

This project is not affiliated with or endorsed by the ABS, the Department of Transport and Planning, National Digital or Kaggle.

## No warranties

The source data is provided by its licensors "as is", without warranties of any kind, as set out in Section 5 of the [CC BY 4.0 licence](https://creativecommons.org/licenses/by/4.0/legalcode). The same applies to the derived data and calculations in this project.

## How this meets the CC BY 4.0 conditions (Section 3(a))

| Condition | Where it is met |
|---|---|
| Identify the creators and anyone they designate for credit | ABS, DTP, and National Digital (publicdata.au) for the republished crash data |
| Keep copyright, licence and disclaimer notices supplied with the material | None besides the licence were supplied with the data. The licence is linked everywhere, and the warranty notice is above |
| Link to the material | Every source is linked in the dashboard footer, `/api/about` and this file |
| Say if it was modified, and keep earlier modification notes | Our changes are listed under *Changes made*. National Digital's change (adding area codes) is kept above |
| State the licence with a link to it | Every attribution links to CC BY 4.0 |
| Don't suggest endorsement | Stated above |

## Where the attribution appears

| Place | How |
|---|---|
| Web dashboard | Footer credits both publishers, with links to the sources and the licence |
| REST API | `GET /api/about` returns each source and licence; the OpenAPI docs at `/api/docs` include the attribution |
| GeoJSON export | `attribution` and `license` fields on `GET /api/suburbs/geojson` |
| Repository | This file, [`README.md`](README.md) and [`data/README.md`](data/README.md) |

## Map tiles

Base map tiles © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under the
[Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
