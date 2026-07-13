# Data Flow — sales_orders vertical slice

End-to-end path for the one implemented source, `sales_orders`, from CSV to
BI-ready mart.

```
sample-data/sales_orders.csv
        │
        ▼  [extract]  (airflow/dags/sales_orders_pipeline.py)
data-lake/raw/sales_orders/<run_id>/sales_orders.csv
        │                                             MetadataClient.start_run/complete_run
        ▼  [clean_and_dedupe]                         -> quarry_metadata.pipeline_runs
  - cast types (order_date, quantity, unit_price, order_amount)
  - drop rows with null order_id
  - drop_duplicates(subset=["order_id"])
        ▼
data-lake/clean/sales_orders/<run_id>/sales_orders.parquet
        │
        ▼  [dq_gate]  (libs/dq_checks)
  - check_schema_match   -> exact column set + dtype kind
  - check_null_rate       -> customer_id <= 10% null, order_amount 0% null
  - check_uniqueness      -> order_id unique
  - check_referential_integrity -> region in {US-EAST, US-WEST, EU-WEST, APAC}
  any failure -> DataQualityError -> AirflowException -> task/DAG run fails
        ▼ (only on pass)
        ▼  [write_curated]
data-lake/curated/sales_orders/<run_id>/sales_orders.parquet
        │  + INSERT into Postgres raw.sales_orders (warehouse staging table)
        │  + MetadataClient.register_dataset("curated.sales_orders", ...)
        ▼  [trigger_dbt_run]  (dbt/)
raw.sales_orders (Postgres, dbt source)
        │
        ▼  dbt: stg_sales_orders, stg_customers      (dbt/models/staging)
        ▼  dbt: int_sales_orders_enriched            (dbt/models/intermediate)
        ▼  dbt: mart_sales_daily                     (dbt/models/marts)
        │
        ▼
   BI (QuickSight / Superset) reads mart_sales_daily
   metadata-api GET /pipelines/sales_orders_pipeline/runs  <- pipeline_runs
   metadata-api GET /catalog                                <- dataset_catalog
```

## Failure semantics

- Every task run is bracketed by `MetadataClient.run(...)`, which writes a
  `running` row at task start and updates it to `success`/`failed` (with
  `error_message`) at task end — including on exception, before the
  exception re-raises to Airflow.
- The DQ gate is a hard stop: `run_checks(..., raise_on_failure=True)`
  raises `DataQualityError`, which the task re-raises as `AirflowException`.
  Airflow's configured retries (3, exponential backoff, see `default_args`
  in the DAG file) apply before the task — and therefore the DAG run — is
  marked failed. `write_curated` never runs on unvalidated data.
- `write_curated` additionally asserts the row count it receives from
  `dq_gate` matches what it reads back from the clean zone, to guard
  against a race/drift between validation and the curated write.
