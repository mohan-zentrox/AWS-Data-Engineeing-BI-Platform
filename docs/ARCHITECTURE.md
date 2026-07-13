# Architecture — Project Quarry

Project Quarry is an AWS-native data engineering and BI platform. This repo
is the **foundation codebase**: infrastructure-as-code plus a working
vertical slice of the batch pipeline, built to be extended by the team in
`docs/TEAM.md`.

## Component map

```
                 ┌─────────────────────────────────────────────────────────┐
                 │                        Orchestration                     │
                 │  Apache Airflow (primary)  +  AWS Step Functions          │
                 │  (AWS-native sub-flows: Glue job starts, SFN executions)  │
                 └───────────────┬─────────────────────────────────────────┘
                                 │ triggers / monitors
                                 ▼
   Source          ┌─────────────────────────┐        ┌─────────────────────┐
   Systems  ───────▶│   AWS Glue + PySpark     │───────▶│  S3 Data Lake        │
   (sales_orders,   │   extract/clean/curate   │        │  raw -> clean ->     │
   Salesforce*,     │   jobs                    │        │  curated (Parquet,  │
   Stripe*, GA*,    └─────────────────────────┘        │  versioned, SSE-KMS) │
   Kinesis*)                                             └──────────┬──────────┘
   (* scaffolded)                                                    │
                                                                      ▼
                                                        ┌─────────────────────────┐
                                                        │  dbt (staging ->         │
                                                        │  intermediate -> marts)  │
                                                        └──────────┬──────────────┘
                                                                    ▼
                                            ┌───────────────────────────────────┐
                                            │  Serving: Amazon Redshift          │
                                            │  Serverless lake query: Athena     │
                                            └───────────────┬───────────────────┘
                                                             ▼
                                            ┌───────────────────────────────────┐
                                            │  BI: QuickSight / Superset          │
                                            └───────────────────────────────────┘

   Cross-cutting:
   - Metadata store (PostgreSQL): run state, watermarks, dataset catalog,
     lineage — written by libs/metadata_client, read by metadata-api.
   - Governance: IAM (terraform/modules/iam), Lake Formation (scaffolded),
     CloudTrail, KMS, Secrets Manager.
   - IaC/CI-CD: Terraform + Docker + ECR + GitHub Actions.
```

## What's implemented vs scaffolded

See the repo root README.md for the authoritative, up-to-date list. In
short: the `sales_orders` vertical slice (S3 data lake IaC, Airflow DAG,
dbt models, metadata API, DQ checks) is real working code. Additional
source connectors, Kinesis streaming, Lake Formation policies, and the cost
dashboard are scaffolded (structure + TODOs referencing FRD sections, no
logic).

## Data lake zone contract

- **raw** — landed exactly as received from the source (schema-on-read).
  `airflow/dags/sales_orders_pipeline.py`'s `extract` task writes here.
- **clean** — typed, deduplicated, Parquet. Written by `clean_and_dedupe`.
  Must pass the DQ gate (`libs/dq_checks`) before promotion.
- **curated** — business-ready, partitioned Parquet, registered in the
  dataset catalog (`quarry_metadata.dataset_catalog`). Written by
  `write_curated`, and loaded into the warehouse staging table dbt reads
  from.

## Metadata store

`libs/metadata_client/schema.sql` defines the `quarry_metadata` Postgres
schema:

- `pipeline_runs` — one row per task execution (start/end/status/rowcount).
- `watermarks` — incremental-extraction cursors per pipeline+dataset.
- `dataset_catalog` — registered datasets across all zones, with
  `last_updated_at` and an `owner_role` (a `docs/TEAM.md` role ID).
- `lineage_edges` — coarse upstream/downstream dataset relationships.

`libs/metadata_client.MetadataClient` is the write-side client used by
Airflow tasks. `metadata-api` is the read-side HTTP API over the same
tables (`GET /pipelines/{name}/runs`, `GET /catalog`).

## Local dev warehouse stand-in

Amazon Redshift is the documented serving warehouse, but requires a running
AWS cluster. For local development, the same Postgres container that hosts
`quarry_metadata` also hosts a `raw` schema (`raw.sales_orders`) that dbt's
`dev` target reads from — Redshift is wire-compatible with Postgres, so the
same SQL in `dbt/models/` is expected to work against a real
`dbt/profiles.yml.example` `redshift` target with no model changes.

## Orchestration split: Airflow vs Step Functions

Airflow (`airflow/dags/sales_orders_pipeline.py`) owns the end-to-end batch
pipeline DAG. Per the BRD, AWS-native sub-flows (e.g. a chain of Glue job
runs that benefit from Step Functions' native retry/catch semantics and
AWS console visibility) are triggered *from* Airflow tasks rather than
duplicating orchestration logic — see the `iam` module's
`InvokeAwsNativeSubFlows` policy statement, which grants the Airflow role
`states:StartExecution` for this purpose. No Step Functions state machine
is defined yet in this vertical slice; the IAM path is prepared for when
one is added.
