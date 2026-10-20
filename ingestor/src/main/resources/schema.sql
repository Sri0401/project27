-- Schema owned by the ingestor. Every statement is idempotent so the job can be re-run safely.
CREATE TABLE IF NOT EXISTS suburb_indicators (
    code               VARCHAR(16)      PRIMARY KEY,
    name               TEXT             NOT NULL,
    state              VARCHAR(8)       NOT NULL,
    latitude           DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude          DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    population         INTEGER          NOT NULL CHECK (population >= 0),
    median_age         NUMERIC(4, 1)    NOT NULL,
    median_weekly_rent INTEGER          NOT NULL CHECK (median_weekly_rent >= 0),
    walk_score         INTEGER          NOT NULL CHECK (walk_score BETWEEN 0 AND 100),
    green_space_pct    NUMERIC(5, 2)    NOT NULL CHECK (green_space_pct BETWEEN 0 AND 100),
    pt_stops           INTEGER          NOT NULL CHECK (pt_stops >= 0),
    reference_year     INTEGER          NOT NULL,
    updated_at         TIMESTAMPTZ      NOT NULL DEFAULT now()
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
