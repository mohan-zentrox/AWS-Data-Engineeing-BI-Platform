"""Salesforce source connector — SCAFFOLD ONLY, not implemented.

Reference: FRD section "Source Systems -> CRM (Salesforce)" and
BRD section "Data Sources & Ingestion".

Intended shape (do not build ahead of the FRD sign-off for this connector):
  - Auth via Simple Salesforce / OAuth2 JWT bearer flow, credentials pulled
    from AWS Secrets Manager at `quarry/<env>/salesforce`.
  - Bulk API 2.0 extraction of Account/Opportunity/Contact objects on a
    watermark (SystemModstamp) read from libs.metadata_client
    MetadataClient.get_watermark/set_watermark, mirroring the pattern used
    by airflow/dags/sales_orders_pipeline.py.
  - Lands extracted records as newline-delimited JSON in the raw zone under
    raw/salesforce/<object>/<run_id>/.
  - Registered as an Airflow DAG (airflow/dags/salesforce_pipeline.py, not
    yet created) parallel to sales_orders_pipeline.py, reusing
    libs/dq_checks for the DQ gate.

TODO(T4-DE2, FRD 4.2 Source Connectors): implement extraction client.
TODO(T4-DE2, FRD 4.2 Source Connectors): implement incremental watermark logic.
TODO(T4-QA1, FRD 7 Data Quality): define Salesforce-specific DQ rule set.
"""

# Intentionally no implementation — see module docstring.
