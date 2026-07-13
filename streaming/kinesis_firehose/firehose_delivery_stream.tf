# Kinesis Firehose delivery stream — SCAFFOLD ONLY, not implemented.
#
# Reference: FRD section 4.3 "Streaming Ingestion". See README.md in this
# directory for the intended design. Left as a placeholder (not wired into
# terraform/environments/dev) so `terraform validate` on the real
# environments does not depend on unfinished streaming resources.
#
# TODO(T4-BE1, FRD 4.3 Streaming Ingestion): define aws_kinesis_firehose_delivery_stream
#   targeting the raw zone S3 bucket (see terraform/modules/s3-data-lake outputs).
# TODO(T4-BE1, FRD 4.3 Streaming Ingestion): define the Lambda transform + IAM role.
# TODO(T4-LEAD, FRD 4.3 Streaming Ingestion): confirm buffering interval / size SLA.
