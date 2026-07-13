"""Stripe source connector — SCAFFOLD ONLY, not implemented.

Reference: FRD section "Source Systems -> Payments (Stripe)" and
BRD section "Data Sources & Ingestion".

Intended shape (do not build ahead of the FRD sign-off for this connector):
  - Auth via restricted Stripe API key from Secrets Manager
    (`quarry/<env>/stripe`).
  - Extract Charges/Invoices/Payouts via the Stripe list API with
    `created[gte]` cursoring, watermark stored via
    libs.metadata_client.MetadataClient.
  - Lands raw JSON in raw/stripe/<object>/<run_id>/, following the same
    raw -> clean -> curated contract as sales_orders_pipeline.py.
  - PII/financial fields subject to Lake Formation column-level policy —
    see governance/lake_formation/ scaffold before implementing.

TODO(T4-DE3, FRD 4.2 Source Connectors): implement extraction client.
TODO(T4-DE3, FRD 4.2 Source Connectors): implement idempotent upsert-on-replay for webhook backfills.
TODO(T4-QA1, FRD 7 Data Quality): define Stripe-specific DQ rule set (currency/amount sanity checks).
"""

# Intentionally no implementation — see module docstring.
