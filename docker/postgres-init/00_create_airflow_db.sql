-- Project Quarry — create Airflow's own metadata database.
--
-- Runs before 01_quarry_metadata_schema.sql (the postgres entrypoint executes
-- /docker-entrypoint-initdb.d/* in filename order) and is applied against the
-- POSTGRES_DB created by the entrypoint.
--
-- Airflow needs a metadata database of its own, kept separate from Project
-- Quarry's `quarry_metadata` tables: Airflow creates ~40 tables of its own in
-- the `public` schema and runs schema migrations against them on every version
-- bump, which has no business sharing a database with the platform's run-state
-- and catalog tables or with dbt's analytics_* schemas.
--
-- Why this exists at all: docker-compose previously let `airflow standalone`
-- fall back to its default SQLite metadata DB with SequentialExecutor. The
-- scheduler and triggerer hold that single file continuously, so the
-- webserver's gunicorn worker could not complete its boot and the UI died
-- within a couple of days of uptime — reported misleadingly as
-- "No response from gunicorn master within N seconds".

CREATE DATABASE airflow;

COMMENT ON DATABASE airflow IS
    'Apache Airflow internal metadata database (DAG runs, task instances, users). Not Project Quarry platform metadata — that lives in the quarry_metadata schema of the quarry_metadata database.';
