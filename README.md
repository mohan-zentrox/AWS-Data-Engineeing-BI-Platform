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

This sandbox has no `terraform` or `docker` binary on it (not installed
anywhere on the machine). Python and git turned out to be present but not
on `PATH` (found at
`C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe` and
`C:\Program Files\Git\cmd\git.exe`), so the following were **actually
executed** in a throwaway venv, not just hand-reviewed:

- `pytest libs/metadata_client/tests libs/dq_checks/tests` — **29 passed**.
- `pytest metadata-api/tests` — **7 passed**. This caught a real bug: the
  SQLite in-memory test DB needs `poolclass=StaticPool`, because FastAPI
  runs sync path operations in a threadpool worker thread, which would
  otherwise get a *different, empty* `:memory:` database than the one
  `Base.metadata.create_all()` populated on the main thread. Fixed in
  `metadata-api/tests/conftest.py`.
- `ruff check libs metadata-api` — **all checks passed** (after removing
  one unused import caught by the run).
- `python -m py_compile` on all 24 `.py` files in the repo — **0 syntax
  errors**.
- `dbt parse --profiles-dir . --project-dir .` — **parsed cleanly**: 4
  models, 21 data tests, 1 source, 0 errors. This caught 4 deprecation
  warnings (generic test arguments should be nested under `arguments:` in
  newer dbt versions) — fixed in the `schema.yml` files.
- `dbt compile` was attempted but requires a live warehouse connection
  (`localhost:5432` — Postgres isn't running in this sandbox, no Docker
  available to start it) and failed with a connection-refused error, as
  expected. `dbt run` / `dbt test` likewise need the real docker-compose
  Postgres and were **not** run here.

**Not executed, hand-reviewed only** (no terraform binary anywhere on this
machine): `terraform fmt -check` and `terraform validate` for all four
module/environment directories. Reviewed by hand for HCL block structure,
required-argument completeness, and AWS provider (v5) resource/attribute
names — including the `use_local_dev_db` conditional-resource-count pattern
in `terraform/modules/postgres-metadata` and the newer
`aws_vpc_security_group_ingress_rule` resource shape. Also not run:
`docker compose up` (no Docker Engine on this machine) and `dbt run`/`dbt
test` against a live warehouse (needs that same Docker Postgres).

The `.github/workflows/ci.yml` pipeline runs `terraform fmt`/`validate`,
`ruff` + `pytest`, and `dbt parse` on every push/PR — treat it as the
authoritative gate for the terraform validation that couldn't be executed
in this sandbox. CI does not yet run `dbt run`/`dbt test` against a live
warehouse (that needs a Postgres service container wired into the
workflow, not present yet) or `docker compose up` — both are still manual
verification steps for now.

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
