# S3 Data Lake module — Project Quarry
#
# Provisions one S3 bucket per data lake zone (raw / clean / curated by
# default; see var.zones). Every bucket is:
#   - versioned (protects against accidental overwrite/delete during Glue/dbt
#     re-runs and gives us point-in-time recovery for curated data)
#   - encrypted at rest (SSE-KMS when a CMK is supplied, else SSE-S3)
#   - fully blocked from public access
#   - forced to TLS-only access via bucket policy
#
# Referenced by: terraform/environments/dev/main.tf
# See docs/ARCHITECTURE.md for the raw -> clean -> curated zone contract.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  bucket_names = {
    for zone in var.zones :
    zone => lower("${var.project}-${var.environment}-${zone}-zone")
  }
  use_kms = var.kms_key_arn != null
}

resource "aws_s3_bucket" "zone" {
  for_each      = local.bucket_names
  bucket        = each.value
  force_destroy = var.force_destroy

  tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    DataZone    = each.key
    ManagedBy   = "terraform"
  })
}

resource "aws_s3_bucket_versioning" "zone" {
  for_each = aws_s3_bucket.zone
  bucket   = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "zone" {
  for_each = aws_s3_bucket.zone
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.use_kms ? "aws:kms" : "AES256"
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = local.use_kms
  }
}

resource "aws_s3_bucket_public_access_block" "zone" {
  for_each = aws_s3_bucket.zone
  bucket   = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "zone" {
  for_each = aws_s3_bucket.zone
  bucket   = each.value.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    filter {
      prefix = ""
    }
  }
}

data "aws_iam_policy_document" "tls_only" {
  for_each = aws_s3_bucket.zone

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [each.value.arn, "${each.value.arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = aws_s3_bucket.zone
  bucket   = each.value.id
  policy   = data.aws_iam_policy_document.tls_only[each.key].json
}
