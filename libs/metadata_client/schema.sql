-- Project Quarry — metadata store schema
--
-- Backs: run state, watermarks, dataset catalog, lineage (BRD/FRD: "Metadata
-- store: PostgreSQL"). Applied automatically to the docker-compose Postgres
-- container via docker-entrypoint-initdb.d (see docker-compose.yml), and is
-- the schema libs/metadata_client and metadata-api both read/write.
--
-- In local dev this same database also hosts the `raw` schema table that
-- the Airflow curated-write task loads into, which dbt then builds
-- staging/intermediate/mart models on top of (see dbt/profiles.yml.example).

CREATE SCHEMA IF NOT EXISTS quarry_metadata;

-- One row per DAG/task run attempt. Written by libs/metadata_client at the
-- start and end of each Airflow task via MetadataClient.start_run /
-- complete_run.
CREATE TABLE IF NOT EXISTS quarry_metadata.pipeline_runs (
    run_id          UUID PRIMARY KEY,
    pipeline_name   TEXT NOT NULL,
    task_name       TEXT,
    dag_run_id      TEXT,
    status          TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    row_count       BIGINT,
    error_message   TEXT,
    extra           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_name
    ON quarry_metadata.pipeline_runs (pipeline_name, started_at DESC);

-- Watermark per pipeline+dataset, used for incremental extraction.
CREATE TABLE IF NOT EXISTS quarry_metadata.watermarks (
    pipeline_name    TEXT NOT NULL,
    dataset_name      TEXT NOT NULL,
    watermark_value   TEXT NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pipeline_name, dataset_name)
);

-- Registered datasets in the platform catalog: one row per zone/table the
-- platform manages. Surfaced by metadata-api's GET /catalog.
CREATE TABLE IF NOT EXISTS quarry_metadata.dataset_catalog (
    dataset_name    TEXT PRIMARY KEY,
    zone            TEXT NOT NULL CHECK (zone IN ('raw', 'clean', 'curated', 'warehouse')),
    location        TEXT NOT NULL,
    owner_role      TEXT NOT NULL,
    description     TEXT,
    last_updated_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Coarse-grained lineage edges: which dataset was derived from which.
-- Enough for the vertical slice; a fuller lineage graph is future work.
CREATE TABLE IF NOT EXISTS quarry_metadata.lineage_edges (
    id              BIGSERIAL PRIMARY KEY,
    upstream_dataset   TEXT NOT NULL REFERENCES quarry_metadata.dataset_catalog (dataset_name),
    downstream_dataset TEXT NOT NULL REFERENCES quarry_metadata.dataset_catalog (dataset_name),
    pipeline_name      TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (upstream_dataset, downstream_dataset, pipeline_name)
);

-- ---------------------------------------------------------------------------
-- Local-dev "warehouse" schema: dbt's Postgres target for staging/int/mart
-- models. In AWS this role is played by Redshift/Athena; Postgres stands in
-- for local development per the FRD's "or from metadata Postgres for local
-- dev" guidance. The Airflow curated-write task loads sales_orders here.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.sales_orders (
    order_id        TEXT,
    customer_id     TEXT,
    customer_name   TEXT,
    order_date      DATE,
    product_sku     TEXT,
    product_name    TEXT,
    quantity        INTEGER,
    unit_price      NUMERIC(12, 2),
    order_amount    NUMERIC(12, 2),
    order_status    TEXT,
    region          TEXT,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
