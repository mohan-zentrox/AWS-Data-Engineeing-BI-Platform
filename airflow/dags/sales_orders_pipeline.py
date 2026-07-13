"""Project Quarry — sales_orders vertical-slice pipeline.

extract (source CSV -> raw zone)
  -> clean_and_dedupe (raw -> typed/deduped Parquet in clean zone)
  -> dq_gate (schema/null/uniqueness/referential checks; fails the DAG run
     on violation)
  -> write_curated (clean -> curated zone Parquet + load into the warehouse
     staging table dbt reads from)
  -> trigger_dbt_run (staging -> intermediate -> mart_sales_daily)

Every task records start/end/status/rowcount to the Postgres metadata store
via libs/metadata_client.MetadataClient, satisfying the platform's run-state
tracking requirement (BRD: "Metadata store: PostgreSQL — run state,
watermarks, catalog, lineage").

Zone storage is a local filesystem path by default (./data-lake/{raw,clean,curated}
at the repo root) so the DAG runs end-to-end without AWS credentials in dev.
Point RAW_ZONE_PATH / CLEAN_ZONE_PATH / CURATED_ZONE_PATH at s3:// URIs (with
s3fs installed) to run the same code against real S3 in higher environments —
no task logic changes, only the path scheme.

Owner: T4-DE1 (per docs/TEAM.md role assignment for the sales_orders slice).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pendulum

# ---------------------------------------------------------------------------
# Make the repo's internal libraries importable.
#
# In a deployed Airflow image these are installed properly via
# `pip install -e libs/metadata_client -e libs/dq_checks` (see
# docker-compose.yml / metadata-api/Dockerfile pattern). For local
# `airflow standalone` runs against this repo checkout, we fall back to
# adding libs/ to sys.path so the DAG file parses and runs without a
# separate install step.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
LIBS_DIR = REPO_ROOT / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))

from airflow.decorators import dag, task  # noqa: E402
from airflow.exceptions import AirflowException  # noqa: E402

from dq_checks import (  # noqa: E402
    DataQualityError,
    check_null_rate,
    check_referential_integrity,
    check_schema_match,
    check_uniqueness,
    run_checks,
)
from metadata_client import MetadataClient  # noqa: E402

PIPELINE_NAME = "sales_orders_pipeline"

# Zone roots. Override via env vars to point at s3:// URIs in deployed
# environments (see .env.example).
RAW_ZONE_ROOT = os.environ.get("RAW_ZONE_PATH", str(REPO_ROOT / "data-lake" / "raw"))
CLEAN_ZONE_ROOT = os.environ.get("CLEAN_ZONE_PATH", str(REPO_ROOT / "data-lake" / "clean"))
CURATED_ZONE_ROOT = os.environ.get("CURATED_ZONE_PATH", str(REPO_ROOT / "data-lake" / "curated"))
SOURCE_CSV_PATH = os.environ.get("SALES_ORDERS_SOURCE_CSV", str(REPO_ROOT / "sample-data" / "sales_orders.csv"))

DQ_NULL_RATE_THRESHOLD = float(os.environ.get("SALES_ORDERS_NULL_RATE_THRESHOLD", "0.10"))
VALID_REGIONS = {"US-EAST", "US-WEST", "EU-WEST", "APAC"}

EXPECTED_CLEAN_SCHEMA = {
    "order_id": "object",
    "customer_id": "object",
    "customer_name": "object",
    "order_date": "datetime",
    "product_sku": "object",
    "product_name": "object",
    "quantity": "int",
    "unit_price": "float",
    "order_amount": "float",
    "order_status": "object",
    "region": "object",
}

default_args = {
    "owner": "T4-DE1",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
}


def _zone_dir(root: str, run_id: str) -> str:
    """Join a zone root with a run-partitioned subdirectory.

    Works for both local paths and s3:// URIs since it's plain string/posix
    joining, not filesystem-specific.
    """
    safe_run_id = run_id.replace(":", "_").replace("+", "_")
    if root.startswith("s3://"):
        return f"{root.rstrip('/')}/sales_orders/{safe_run_id}"
    return str(Path(root) / "sales_orders" / safe_run_id)


def _ensure_local_parent(path: str) -> None:
    if not path.startswith("s3://"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)


@dag(
    dag_id=PIPELINE_NAME,
    description="Extract sample sales_orders CSV, clean/dedupe, DQ-gate, curate, then trigger dbt.",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=default_args,
    tags=["quarry", "sales_orders", "vertical-slice"],
)
def sales_orders_pipeline():
    @task
    def extract(**context: Any) -> str:
        """Land the source CSV in the raw zone, unmodified (schema-on-read)."""
        import pandas as pd

        run_id = context["run_id"]
        client = MetadataClient()
        with client.run(PIPELINE_NAME, task_name="extract", dag_run_id=run_id) as set_row_count:
            df = pd.read_csv(SOURCE_CSV_PATH)

            raw_dir = _zone_dir(RAW_ZONE_ROOT, run_id)
            raw_path = f"{raw_dir}/sales_orders.csv"
            _ensure_local_parent(raw_path)
            df.to_csv(raw_path, index=False)

            set_row_count(len(df))
        return raw_path

    @task
    def clean_and_dedupe(raw_path: str, **context: Any) -> str:
        """Type, rename-normalize, and dedupe rows; write typed Parquet to the clean zone."""
        import pandas as pd

        run_id = context["run_id"]
        client = MetadataClient()
        with client.run(PIPELINE_NAME, task_name="clean_and_dedupe", dag_run_id=run_id) as set_row_count:
            df = pd.read_csv(raw_path)

            df["order_id"] = df["order_id"].astype("string")
            df["customer_id"] = df["customer_id"].astype("string")
            df["customer_name"] = df["customer_name"].astype("string")
            df["product_sku"] = df["product_sku"].astype("string")
            df["product_name"] = df["product_name"].astype("string")
            df["order_status"] = df["order_status"].astype("string").str.upper()
            df["region"] = df["region"].astype("string").str.upper()
            df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
            df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").astype("float64")
            df["order_amount"] = pd.to_numeric(df["order_amount"], errors="coerce").astype("float64")

            before = len(df)
            df = df.dropna(subset=["order_id"])
            df = df.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)
            deduped = before - len(df)

            # cast back to plain object/int64 dtypes expected downstream by
            # dq_checks.check_schema_match (which understands
            # int/float/object/bool/datetime dtype "kinds").
            df["quantity"] = df["quantity"].astype("int64")
            for col in ["order_id", "customer_id", "customer_name", "product_sku", "product_name", "order_status", "region"]:
                df[col] = df[col].astype("object")

            clean_dir = _zone_dir(CLEAN_ZONE_ROOT, run_id)
            clean_path = f"{clean_dir}/sales_orders.parquet"
            _ensure_local_parent(clean_path)
            df.to_parquet(clean_path, index=False)

            set_row_count(len(df))
            context["ti"].xcom_push(key="deduped_row_count", value=deduped)
        return clean_path

    @task
    def dq_gate(clean_path: str, **context: Any) -> int:
        """Schema/null/uniqueness/referential checks. Raises (fails the DAG) on violation."""
        import pandas as pd

        run_id = context["run_id"]
        client = MetadataClient()
        with client.run(PIPELINE_NAME, task_name="dq_gate", dag_run_id=run_id) as set_row_count:
            df = pd.read_parquet(clean_path)

            results = [
                check_schema_match(df, EXPECTED_CLEAN_SCHEMA),
                check_null_rate(df, "customer_id", max_null_rate=DQ_NULL_RATE_THRESHOLD),
                check_null_rate(df, "order_amount", max_null_rate=0.0),
                check_uniqueness(df, "order_id"),
                check_referential_integrity(df, "region", VALID_REGIONS, allow_nulls=False),
            ]

            try:
                run_checks(results, raise_on_failure=True)
            except DataQualityError as exc:
                # Surface as an AirflowException so retries/alerting behave
                # the way they would for any other task failure.
                raise AirflowException(str(exc)) from exc

            set_row_count(len(df))
        return len(df)

    @task
    def write_curated(clean_path: str, row_count: int, **context: Any) -> dict[str, Any]:
        """Write curated Parquet and load the warehouse staging table dbt reads from."""
        import pandas as pd

        run_id = context["run_id"]
        client = MetadataClient()
        with client.run(PIPELINE_NAME, task_name="write_curated", dag_run_id=run_id) as set_row_count:
            df = pd.read_parquet(clean_path)
            if len(df) != row_count:
                raise AirflowException(
                    f"Row count drifted between dq_gate ({row_count}) and write_curated ({len(df)}); "
                    "aborting curated write to avoid silently curating unvalidated rows."
                )
            df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
            df["ingested_at"] = pendulum.now("UTC").to_iso8601_string()

            curated_dir = _zone_dir(CURATED_ZONE_ROOT, run_id)
            curated_path = f"{curated_dir}/sales_orders.parquet"
            _ensure_local_parent(curated_path)
            df.to_parquet(curated_path, index=False)

            _load_warehouse_staging_table(df)

            client.register_dataset(
                dataset_name="curated.sales_orders",
                zone="curated",
                location=curated_path,
                owner_role="T4-DE1",
                description="Curated, deduplicated sales_orders — vertical slice source for dbt staging.",
            )
            client.touch_dataset("curated.sales_orders")

            set_row_count(len(df))
        return {"curated_path": curated_path, "row_count": int(len(df))}

    @task
    def trigger_dbt_run(curated_result: dict[str, Any], **context: Any) -> str:
        """Run `dbt run` against the staging/intermediate/mart models for this slice."""
        import subprocess

        run_id = context["run_id"]
        client = MetadataClient()
        dbt_project_dir = str(REPO_ROOT / "dbt")
        dbt_profiles_dir = os.environ.get("DBT_PROFILES_DIR", dbt_project_dir)

        with client.run(PIPELINE_NAME, task_name="trigger_dbt_run", dag_run_id=run_id) as set_row_count:
            cmd = [
                "dbt",
                "run",
                "--project-dir",
                dbt_project_dir,
                "--profiles-dir",
                dbt_profiles_dir,
                "--select",
                "staging.stg_sales_orders staging.stg_customers intermediate.int_sales_orders_enriched marts.mart_sales_daily",
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=True)
                output = result.stdout
            except FileNotFoundError as exc:
                raise AirflowException(
                    "dbt CLI not found on PATH. Install dbt-postgres (see dbt/README / requirements) "
                    "to run this task; DAG code itself is complete."
                ) from exc
            except subprocess.CalledProcessError as exc:
                raise AirflowException(f"dbt run failed:\n{exc.stdout}\n{exc.stderr}") from exc

            set_row_count(curated_result.get("row_count"))
        return output

    raw_path = extract()
    clean_path = clean_and_dedupe(raw_path)
    validated_row_count = dq_gate(clean_path)
    curated_result = write_curated(clean_path, validated_row_count)
    trigger_dbt_run(curated_result)


def _load_warehouse_staging_table(df) -> None:
    """Load curated rows into the Postgres `raw.sales_orders` table dbt reads from.

    Postgres stands in for Redshift in local dev (see libs/metadata_client/schema.sql
    for the `raw` schema DDL and dbt/profiles.yml.example for the dbt target).
    """
    import sqlalchemy

    warehouse_url = os.environ.get("WAREHOUSE_DATABASE_URL") or os.environ.get("METADATA_DATABASE_URL")
    if not warehouse_url:
        raise AirflowException(
            "WAREHOUSE_DATABASE_URL (or METADATA_DATABASE_URL) must be set to load the dbt staging table."
        )

    engine = sqlalchemy.create_engine(warehouse_url)
    load_df = df.rename(columns={}).copy()
    load_df["loaded_at"] = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text("TRUNCATE TABLE raw.sales_orders"))
        load_df.to_sql("sales_orders", conn, schema="raw", if_exists="append", index=False)


sales_orders_pipeline()
