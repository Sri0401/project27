-- Schema owned by the ingestor. Every statement is idempotent so the job can be re-run safely.

-- The table is a snapshot that is fully reloaded on every run. If it exists with an older shape
-- (anything without the newest column), drop it so CREATE TABLE below builds the current version.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'suburb_indicators')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'suburb_indicators' AND column_name = 'road_crashes_per_year') THEN
        DROP TABLE suburb_indicators;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS suburb_indicators (
    code                    VARCHAR(16)      PRIMARY KEY,
    name                    TEXT             NOT NULL,
    state                   VARCHAR(8)       NOT NULL,
    latitude                DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude               DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    area_sqkm               NUMERIC(12, 4)   NOT NULL CHECK (area_sqkm > 0),
    population              INTEGER          NOT NULL CHECK (population >= 0),
    median_age              NUMERIC(4, 1)    NOT NULL,
    median_weekly_rent      INTEGER          NOT NULL CHECK (median_weekly_rent >= 0),
    median_household_income INTEGER          NOT NULL CHECK (median_household_income >= 0),
    green_space_pct         NUMERIC(5, 2)    NOT NULL CHECK (green_space_pct BETWEEN 0 AND 100),
    pt_stops                INTEGER          NOT NULL CHECK (pt_stops >= 0),
    road_crashes_per_year   NUMERIC(10, 1)   NOT NULL CHECK (road_crashes_per_year >= 0),
    reference_year          INTEGER          NOT NULL,
    updated_at              TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_suburb_indicators_state ON suburb_indicators (state);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id            BIGSERIAL   PRIMARY KEY,
    source        TEXT        NOT NULL,
    rows_loaded   INTEGER     NOT NULL,
    rows_rejected INTEGER     NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
