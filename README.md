# Project Quarry — AWS Data Engineering & BI Platform

This repository is **infrastructure-as-code and pipeline code**, not a CRUD
web application. It is the foundation the data engineering team (see
`docs/TEAM.md` for role assignments — role IDs only, per the source
BRD/FRD/SRS compliance rule) extends going forward.

Tech stack (from the team's BRD/FRD/SRS): S3 (raw/clean/curated, Parquet),
AWS Glue + PySpark + dbt, Apache Airflow + AWS Step Functions, Redshift +
Athena, QuickSight/Superset, PostgreSQL metadata store, IAM/Lake
Formation/CloudTrail/KMS/Secrets Manager, Terraform + Docker + ECR + GitHub
Actions.

## What's fully implemented (real, working code)

A single vertical slice — the `sales_orders` source, CSV to mart — built
end to end so the pattern is copy-able for every future source:

| Area | Path | Notes |
|---|---|---|
| S3 data lake IaC | `terraform/modules/s3-data-lake` | 3 versioned, SSE-KMS-ready (falls back to SSE-S3), TLS-only, public-access-blocked buckets |
| Least-privilege IAM | `terraform/modules/iam` | Scoped Glue and Airflow roles — no wildcard S3 resources |
| Metadata Postgres IaC | `terraform/modules/postgres-metadata` | RDS module with a `use_local_dev_db` toggle so dev provisions zero AWS resources |
| Dev environment root | `terraform/environments/dev` | Wires the three modules together |
| Airflow DAG | `airflow/dags/sales_orders_pipeline.py` | TaskFlow API: extract → clean/dedupe → DQ gate → curated write → trigger dbt; retries with exponential backoff; every task writes run state to Postgres |
| Metadata client library | `libs/metadata_client/` | `MetadataClient` (start/complete run, watermarks, catalog, lineage) + `schema.sql` + unit tests |
| DQ checks library | `libs/dq_checks/` | schema match, null-rate, uniqueness, referential-integrity checks + unit tests |
| dbt project | `dbt/` | `stg_sales_orders`, `stg_customers` → `int_sales_orders_enriched` → `mart_sales_daily`, with `not_null`/`unique`/`accepted_values`/`relationships` tests and two singular tests |
| Metadata/status API | `metadata-api/` | FastAPI: `GET /pipelines/{name}/runs`, `GET /catalog`, `GET /health` + pytest suite (SQLite-backed, no live DB needed) |
| Sample data | `sample-data/sales_orders.csv` | 27 synthetic rows incl. one duplicate order and one null `customer_id`, to exercise the dedupe/DQ logic |
| Local dev stack | `docker-compose.yml` | Postgres (metadata store + warehouse stand-in), `metadata-api`, `airflow standalone` |
| CI | `.github/workflows/ci.yml` | `terraform fmt`/`validate` per module, `ruff` + `pytest` for libs/metadata-api, `dbt parse` |

## What's scaffolded (structure + TODOs only, no logic)

Per the explicit scope for this foundation build — these are intentionally
**not implemented**, so the next engineer doesn't have to unwind
half-built logic:

- `connectors/salesforce/`, `connectors/stripe/`, `connectors/ga/` — additional source connectors
- `streaming/kinesis_firehose/` — Kinesis Firehose streaming ingestion
- `governance/lake_formation/` — Lake Formation column-level governance policies
- `cost-dashboard/` — cost observability dashboard

Every scaffold file has `TODO(<role ID>, FRD <section>)` comments pointing
at who owns it and what to build.

## Running locally

```
git clone <repo>
cd data_engineering_repo
cp .env.example .env        # fill in / leave defaults for local dev
docker compose up --build
```

- Airflow UI: http://localhost:8080 (the `airflow standalone` container
  prints its generated admin password to `docker compose logs airflow` on
  first boot). Trigger the `sales_orders_pipeline` DAG manually.
- metadata-api: http://localhost:8000/docs (OpenAPI UI) —
  `GET /pipelines/sales_orders_pipeline/runs`, `GET /catalog`.
- Postgres: `localhost:5432`, db `quarry_metadata`, user `quarry_admin` /
  password `quarry_dev_password` (dev-only, see `.env.example`).

Running dbt directly against the same Postgres (outside Airflow's
`trigger_dbt_run` task):

```
cd dbt
pip install -r requirements.txt
cp profiles.yml.example profiles.yml   # fill in real values, or rely on the env_var() defaults
export DBT_PROFILES_DIR=.
dbt run
dbt test
```

Running the pipeline libraries' tests directly (see Verification below for
what this sandbox could actually execute):

```
pip install -r libs/metadata_client/requirements.txt
pip install -r libs/dq_checks/requirements.txt
pip install -r metadata-api/requirements.txt
pytest libs/metadata_client/tests libs/dq_checks/tests
cd metadata-api && pytest tests
```

## Verification status (read this before trusting green checkmarks)

**This build sandbox has no working `python`, `git`, `terraform`, or
`docker` binaries** (only a Windows Store App-Execution-Alias stub for
`python`, which does not run). Every piece of code in this repo was
**hand-reviewed for syntactic and semantic correctness** — Terraform HCL
block structure, resource/attribute names against the AWS provider,
Python import graphs, SQL — but **none of the following were actually
executed here**:

- `terraform fmt -check` / `terraform validate` (all four module/env
  directories)
- `pytest` for `libs/metadata_client`, `libs/dq_checks`, `metadata-api`
- `dbt parse` / `dbt run` / `dbt test`
- `docker compose up`

The `.github/workflows/ci.yml` pipeline runs all of the above on every
push/PR and is the real verification gate — **run CI (or the commands
above locally) before treating this code as validated**, and treat this
foundation build as reviewed-by-inspection rather than test-verified until
then. If you find a bug CI would have caught, that is expected for a
first pass built without a runnable toolchain — please fix forward.

## Repository layout

```
terraform/{modules/{s3-data-lake,iam,postgres-metadata},environments/dev}
airflow/{dags,plugins}
dbt/{models/{staging,intermediate,marts},tests,seeds,macros}
libs/{metadata_client,dq_checks}/{*.py,tests/}
metadata-api/{app/{main.py,db.py,models.py,schemas.py,routers/},tests/}
docs/{ARCHITECTURE.md,TEAM.md,DATA_FLOW.md}
connectors/{salesforce,stripe,ga}          # scaffold
streaming/kinesis_firehose                 # scaffold
governance/lake_formation                  # scaffold
cost-dashboard                             # scaffold
sample-data/sales_orders.csv
docker-compose.yml, .env.example, .gitignore
```

See `docs/ARCHITECTURE.md` for the component diagram and `docs/DATA_FLOW.md`
for the exact field-level transformation path through the vertical slice.
