# Team — Project Quarry

Per the source BRD/FRD/SRS compliance rule, team members are referenced
**only by role ID** in this repository — never by real name — in code,
comments, commit messages, IAM/Terraform tags, and documentation.

| Role ID   | Role                                | Primary Responsibility (this repo)                                                |
|-----------|--------------------------------------|-------------------------------------------------------------------------------------|
| T4-LEAD   | Data Engineering Lead, AWS           | Architecture sign-off, IAM/Lake Formation grant review, environment promotion gate  |
| T4-DE1    | Data Engineer                        | `sales_orders_pipeline` DAG (owner), curated zone writes, dataset catalog registration |
| T4-DE2    | Data Engineer                        | Salesforce connector (scaffolded, `connectors/salesforce/`)                         |
| T4-DE3    | Data Engineer                        | Stripe connector (scaffolded, `connectors/stripe/`)                                 |
| T4-DATA1  | Analytics / ETL Engineer             | dbt models (`dbt/models/`), GA connector (scaffolded, `connectors/ga/`)             |
| T4-BE1    | Platform / Backend Engineer          | `metadata-api` service, Terraform modules, streaming + governance scaffolds         |
| T4-QA1    | QA Automation Engineer               | `libs/dq_checks` test coverage, `metadata-api` and `libs/metadata_client` test suites |

## Ownership map

| Component                                   | Owner Role ID |
|----------------------------------------------|---------------|
| `terraform/modules/s3-data-lake`              | T4-BE1        |
| `terraform/modules/iam`                       | T4-BE1        |
| `terraform/modules/postgres-metadata`         | T4-BE1        |
| `airflow/dags/sales_orders_pipeline.py`       | T4-DE1        |
| `libs/metadata_client/`                       | T4-DE1        |
| `libs/dq_checks/`                             | T4-QA1        |
| `dbt/models/staging`, `intermediate`, `marts` | T4-DATA1      |
| `metadata-api/`                               | T4-BE1        |
| `connectors/salesforce/`                      | T4-DE2 (scaffold) |
| `connectors/stripe/`                          | T4-DE3 (scaffold) |
| `connectors/ga/`                              | T4-DATA1 (scaffold) |
| `streaming/kinesis_firehose/`                 | T4-BE1 (scaffold) |
| `governance/lake_formation/`                  | T4-BE1 (scaffold), sign-off T4-LEAD |
| `cost-dashboard/`                             | T4-LEAD (scaffold) |

This table is the single source of truth for role assignment in this repo.
Do not introduce real names anywhere in this codebase.
