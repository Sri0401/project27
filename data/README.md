# Sample data

`suburbs_sample.csv` holds **illustrative sample values** for 20 Melbourne suburbs. The coordinates are approximate suburb centres. The indicator values are made up for demonstration and are **not official statistics**.

To use real data, replace the file with indicators from an open source such as the
[AURIN Data Provider](https://data.aurin.org.au/), the [ABS Census DataPacks](https://www.abs.gov.au/census/find-census-data/datapacks)
or [data.vic.gov.au](https://www.data.vic.gov.au/). Keep the same header row, then re-run the ingestor.

| Column | Meaning |
|---|---|
| `code` | Short unique suburb id (letters, digits, `-`, max 16 chars) |
| `walk_score` | Walkability, 0 to 100 |
| `green_space_pct` | Share of land that is public green space, 0 to 100 |
| `pt_stops` | Number of public transport stops |
| `median_weekly_rent` | AUD per week |
