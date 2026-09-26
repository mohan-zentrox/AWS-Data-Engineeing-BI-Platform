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

First boot takes a few minutes: the `airflow` container installs
`airflow/requirements.txt` plus the two internal libs, then builds a
*separate* venv at `/opt/airflow/dbt-venv` for dbt (dbt and Airflow 2.9 pin
incompatible `sqlalchemy`/`jinja2` ranges, so they must not share an
environment — `DBT_EXECUTABLE` points the `trigger_dbt_run` task at that
venv). The venv lives on the `quarry_airflow_home` volume, so it is built
once, not on every boot.

- Airflow UI: http://localhost:8080. Get the generated admin password with:
  ```
  docker compose exec airflow cat /opt/airflow/standalone_admin_password.txt
  ```
  (`airflow standalone` also prints it once on first boot, but the file
  survives container restarts, which the log line does not.) Then trigger the
  `sales_orders_pipeline` DAG from the UI — or from the CLI:
  ```
  docker compose exec airflow airflow dags unpause sales_orders_pipeline
  docker compose exec airflow airflow dags trigger sales_orders_pipeline
  ```
- metadata-api: http://localhost:8000/docs (OpenAPI UI) —
  `GET /pipelines/sales_orders_pipeline/runs`, `GET /catalog`.
- Postgres: `localhost:5432`, db `quarry_metadata`, user `quarry_admin` /
  password `quarry_dev_password` (dev-only, see `.env.example`).

If another local project already binds 5432/8000/8080, override the host
ports (in `.env` or the shell) rather than editing the compose file:

```
POSTGRES_PORT=15433 METADATA_API_PORT=18001 AIRFLOW_PORT=18081 docker compose up -d
```

**When `libs/metadata_client/schema.sql` changes**, remember it is applied via
`docker-entrypoint-initdb.d`, which only runs on *first* initialisation of the
Postgres volume. Existing stacks need `docker compose down -v` (destroys local
data) or a manual `psql` migration.

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

Running the pipeline libraries' tests directly:

```
pip install -r libs/metadata_client/requirements.txt
pip install -r libs/dq_checks/requirements.txt
pip install -r metadata-api/requirements.txt
pytest libs/metadata_client/tests libs/dq_checks/tests
cd metadata-api && pytest tests
```

## Verification status

The vertical slice has been **run end to end from a clean slate**
(`docker compose down -v`, then `docker compose up -d`, then the DAG
triggered — nothing pre-seeded) on Docker 29.1.3. Verified results:

| Check | Result |
|---|---|
| All 5 DAG tasks (`extract` → `clean_and_dedupe` → `dq_gate` → `write_curated` → `trigger_dbt_run`) | success; 0 failed task runs recorded in `pipeline_runs` |
| `raw.sales_orders` after load | 26 rows (27 CSV rows − 1 duplicate `order_id`), all 26 with `ingested_at` populated |
| Lake zones written to `data-lake/{raw,clean,curated}` | raw CSV + clean/curated Parquet, run-partitioned |
| `dbt run` (via `trigger_dbt_run`) | 4 models built into `analytics_staging` / `analytics_intermediate` / `analytics_marts` |
| `dbt test` | **PASS=19 WARN=2 ERROR=0** — the 2 warnings are the deliberate null `customer_id` row (see below) |
| Revenue reconciliation raw → mart | 4357.25 on both sides; mart has 24 `(order_date, region)` rows |
| `metadata-api` | `GET /health`, `GET /catalog` (1 registered dataset) and `GET /pipelines/sales_orders_pipeline/runs` all HTTP 200 |
| Airflow UI | reachable; `/health` reports metadatabase, scheduler and triggerer healthy |
| `pytest` (libs + metadata-api) | 44 passed (35 + 9) |
| `ruff check libs metadata-api airflow connectors` | all checks passed |
| `dbt parse` | 4 models, 21 data tests, 1 source, 0 errors |

**Still not executed**: `terraform fmt -check` and `terraform validate` — no
`terraform` binary on the build machine. Hand-reviewed for HCL block
structure, required-argument completeness, and AWS provider (v5)
resource/attribute names, including the `use_local_dev_db`
conditional-resource-count pattern in `terraform/modules/postgres-metadata`
and the newer `aws_vpc_security_group_ingress_rule` shape.
`.github/workflows/ci.yml` runs both per module on every push/PR — treat CI
as the authoritative gate there.

### Why two dbt tests are warn-level, not error-level

`sample-data/sales_orders.csv` deliberately contains one row with a null
`customer_id`, and the DAG's `dq_gate` deliberately tolerates it
(`check_null_rate` on `customer_id`, threshold
`SALES_ORDERS_NULL_RATE_THRESHOLD`, default 10%) — that bounded null rate is
specified behaviour, not a defect. Staging preserves source fidelity, so an
error-level `not_null` on `stg_sales_orders.customer_id` /
`int_sales_orders_enriched.customer_id` would fail `dbt test` on data the
pipeline is specified to accept. Those two tests are therefore
`severity: warn`: the condition stays visible in every `dbt test` run, while
`dq_gate` remains the hard gate that fails the pipeline above threshold. The
`relationships` test still enforces FK validity for non-null values, and the
other 19 tests remain error-level.

If the platform later requires a complete customer FK, the upgrade path is an
explicit `UNKNOWN` dimension member in `stg_customers` plus a `coalesce` in
staging — not silently filtering the rows out, which would break the revenue
reconciliation above.

### What the first real end-to-end run caught

Everything below was latent in a codebase whose unit tests, lint and `dbt
parse` were all green. Each one blocked the pipeline at runtime:

1. `MetadataClient` passed the SQLAlchemy-style DSN
   (`postgresql+psycopg2://…`, as set in `docker-compose.yml` and
   `.env.example`) straight to `psycopg2.connect()`, which libpq rejects — so
   every task failed on its first line. Now normalised in
   `libs/metadata_client/client.py`.
2. `write_curated` wrote an `ingested_at` column that did not exist in
   `raw.sales_orders`, so the warehouse load failed. Column added to
   `schema.sql`, and the value is now a real timestamp rather than an ISO
   string (pandas binds object-dtype columns as TEXT, which Postgres refuses
   for a `timestamptz` target).
3. The dbt CLI was never installed in the Airflow container, so
   `trigger_dbt_run` could only ever raise. Now installed into its own venv.
4. `REPO_ROOT` resolves to `/` inside the container (DAGs live at
   `/opt/airflow/dags`), so `--project-dir` pointed at a non-existent `/dbt`.
   Now overridable via `DBT_PROJECT_DIR`.
5. dbt inside the container resolved `WAREHOUSE_HOST` to its `localhost`
   default instead of the `postgres` service, so it could not reach the
   warehouse. Now set explicitly.
6. `airflow/requirements.txt` asked for `sqlalchemy>=2.0`, which uninstalled
   the image's 1.4.52 and broke Airflow itself (2.9.3 pins `<2.0`). Now
   pinned compatibly.
7. Two error-level dbt `not_null` tests contradicted the DQ gate's tolerated
   null rate (see the section above).
8. `GET /pipelines/{name}/runs` returned 500 against real Postgres: psycopg2
   returns `uuid.UUID` for a `UUID` column while the response schema expects
   `str`. The SQLite-backed test suite returns `str`, so it never caught
   this. Fixed in `metadata-api/app/models.py` (dialect-aware column type)
   plus a schema-level coercion, with regression tests for both.
9. The Airflow webserver shut itself down — "No response from gunicorn master
   within 120 seconds" — under bind-mount latency, leaving a working
   scheduler but no UI. Timeouts raised and worker count reduced in
   `docker-compose.yml`.

CI does not yet run `dbt run`/`dbt test` against a live warehouse (that needs
a Postgres service container wired into the workflow) or `docker compose up`,
so the end-to-end run above remains a manual verification step.

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
