"""Google Analytics (GA4) source connector — SCAFFOLD ONLY, not implemented.

Reference: FRD section "Source Systems -> Web Analytics (GA4)" and
BRD section "Data Sources & Ingestion".

Intended shape (do not build ahead of the FRD sign-off for this connector):
  - Auth via GA4 Data API service account credentials from Secrets Manager
    (`quarry/<env>/ga4`).
  - Extract daily aggregate reports (sessions, conversions, channel
    grouping) via the runReport API, one partition per report date.
  - Lands raw JSON/CSV exports in raw/ga4/<report>/<run_id>/.
  - Downstream mart likely joins to mart_sales_daily (see
    dbt/models/marts/mart_sales_daily.sql) on order_date for a
    marketing-attribution view — out of scope for the current slice.

TODO(T4-DATA1, FRD 4.2 Source Connectors): implement GA4 Data API client.
TODO(T4-DATA1, FRD 4.2 Source Connectors): define report -> dataset mapping.
TODO(T4-QA1, FRD 7 Data Quality): define GA4-specific DQ rule set (session/date continuity).
"""

# Intentionally no implementation — see module docstring.
