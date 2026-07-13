# Kinesis Firehose Streaming Ingestion — SCAFFOLD ONLY

Reference: FRD section "Ingestion -> Streaming (near-real-time events)" and
BRD section "Non-Functional Requirements -> Latency".

Not implemented. This directory exists to hold the streaming ingestion path
once the FRD's near-real-time event sources (e.g. clickstream, IoT/device
events) are scoped in detail.

## Intended shape

- `firehose_delivery_stream.tf` (Terraform, not yet written): a Kinesis Data
  Firehose delivery stream with a Lambda transform (buffering + light
  schema validation) writing directly into the **raw** zone S3 bucket
  provisioned by `terraform/modules/s3-data-lake`, under
  `raw/streaming/<source>/`.
- A dynamic-partitioning configuration keyed on event date/hour so Glue
  crawlers can discover new partitions without a full re-crawl.
- A companion Glue streaming job (AWS Glue + PySpark structured streaming)
  to micro-batch clean/curate streamed events, parallel to the batch
  sales_orders_pipeline.py DAG.
- CloudWatch alarms on delivery stream error rate, feeding the same
  observability stack as the batch pipelines.

TODO(T4-BE1, FRD 4.3 Streaming Ingestion): design Firehose delivery stream + Lambda transform.
TODO(T4-LEAD, FRD 4.3 Streaming Ingestion): confirm event source list and SLA before implementation.
TODO(T4-DE1, FRD 4.3 Streaming Ingestion): design streaming clean/curate Glue job.
