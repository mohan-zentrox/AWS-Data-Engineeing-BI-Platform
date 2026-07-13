# Cost Dashboard — SCAFFOLD ONLY

Reference: FRD section "Operations -> Cost Observability" and BRD section
"Non-Functional Requirements -> Cost Governance".

Not implemented. This directory exists to hold the AWS cost dashboard
(Glue/Redshift/S3/Athena spend attributed per pipeline and per data zone)
once the FRD's cost-allocation tagging strategy is finalized.

## Intended shape

- Cost allocation tags (`Project=project-quarry`, `Environment`,
  `DataZone`, `Pipeline`) already applied by `terraform/modules/s3-data-lake`
  and `terraform/modules/iam` (see each module's `tags` variable) — this
  dashboard is the consumer of those tags via AWS Cost Explorer / CUR.
- A QuickSight dashboard (or Superset, per BRD's BI tooling choice) sourced
  from the Cost and Usage Report (CUR) exported to the curated zone bucket.
- A scheduled Glue job to aggregate CUR data into a `cost_by_pipeline` mart,
  parallel in spirit to `dbt/models/marts/mart_sales_daily.sql`.

TODO(T4-LEAD, FRD 6.2 Cost Observability): finalize cost allocation tag taxonomy.
TODO(T4-DATA1, FRD 6.2 Cost Observability): build cost_by_pipeline dbt/Glue aggregation.
TODO(T4-BE1, FRD 6.2 Cost Observability): stand up CUR export + QuickSight/Superset dashboard.
