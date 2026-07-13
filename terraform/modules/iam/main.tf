# IAM module — Project Quarry
#
# Least-privilege roles for the two AWS-native compute identities in the
# platform:
#   - glue role: assumed by AWS Glue jobs/crawlers that read raw, write
#     clean/curated Parquet, and register tables in the Glue Data Catalog.
#   - airflow role: assumed by the Airflow workers/MWAA environment that
#     orchestrate the pipeline (S3 read/write for staging files, and
#     permission to start Glue jobs / Step Functions executions).
#
# Both roles scope S3 access down to the specific data lake bucket ARNs
# passed in from the s3-data-lake module outputs — no wildcard resources.
#
# Referenced by: terraform/environments/dev/main.tf

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
  name_prefix   = "${var.project}-${var.environment}"
  bucket_objs   = [for arn in var.data_lake_bucket_arns : "${arn}/*"]
  bucket_bases  = var.data_lake_bucket_arns
  has_kms       = var.kms_key_arn != null
  has_glue_dbs  = length(var.glue_database_arns) > 0
}

# ---------------------------------------------------------------------------
# Glue role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "glue_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "${local.name_prefix}-glue-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
  tags               = merge(var.tags, { Project = var.project, Environment = var.environment })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

data "aws_iam_policy_document" "glue_s3_access" {
  statement {
    sid       = "ListDataLakeBuckets"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = local.bucket_bases
  }

  statement {
    sid    = "ReadWriteDataLakeObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObjectVersion",
    ]
    resources = local.bucket_objs
  }

  dynamic "statement" {
    for_each = local.has_kms ? [1] : []
    content {
      sid       = "UseDataLakeCmk"
      effect    = "Allow"
      actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
      resources = [var.kms_key_arn]
    }
  }

  dynamic "statement" {
    for_each = local.has_glue_dbs ? [1] : []
    content {
      sid    = "GlueCatalogAccess"
      effect = "Allow"
      actions = [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:GetTables",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:GetPartitions",
        "glue:BatchCreatePartition",
      ]
      resources = var.glue_database_arns
    }
  }
}

resource "aws_iam_role_policy" "glue_data_lake" {
  name   = "${local.name_prefix}-glue-data-lake-access"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue_s3_access.json
}

# ---------------------------------------------------------------------------
# Airflow role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "airflow_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["airflow.amazonaws.com", "airflow-env.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "airflow" {
  name               = "${local.name_prefix}-airflow-role"
  assume_role_policy = data.aws_iam_policy_document.airflow_assume.json
  tags               = merge(var.tags, { Project = var.project, Environment = var.environment })
}

data "aws_iam_policy_document" "airflow_access" {
  statement {
    sid       = "ListDataLakeBuckets"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = local.bucket_bases
  }

  statement {
    sid    = "ReadWriteDataLakeObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:GetObjectVersion",
    ]
    resources = local.bucket_objs
  }

  statement {
    sid    = "InvokeAwsNativeSubFlows"
    effect = "Allow"
    actions = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns",
      "glue:BatchStopJobRun",
      "states:StartExecution",
      "states:DescribeExecution",
      "states:StopExecution",
    ]
    resources = ["*"] # Step Functions state machine / Glue job ARNs are created per-pipeline; scope further once known.
  }

  statement {
    sid    = "AirflowLogging"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:GetLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:log-group:/quarry/airflow/*"]
  }

  dynamic "statement" {
    for_each = local.has_kms ? [1] : []
    content {
      sid       = "UseDataLakeCmk"
      effect    = "Allow"
      actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
      resources = [var.kms_key_arn]
    }
  }
}

resource "aws_iam_role_policy" "airflow_data_lake" {
  name   = "${local.name_prefix}-airflow-orchestration-access"
  role   = aws_iam_role.airflow.id
  policy = data.aws_iam_policy_document.airflow_access.json
}

# Secrets Manager read access for both roles (metadata DB creds, API keys for
# source connectors). Scoped by name prefix so new secrets are automatically
# in-scope without a Terraform change, but nothing outside the project is.
data "aws_iam_policy_document" "secrets_read" {
  statement {
    sid       = "ReadProjectSecrets"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = ["arn:aws:secretsmanager:*:*:secret:${var.project}/${var.environment}/*"]
  }
}

resource "aws_iam_role_policy" "glue_secrets" {
  name   = "${local.name_prefix}-glue-secrets-access"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.secrets_read.json
}

resource "aws_iam_role_policy" "airflow_secrets" {
  name   = "${local.name_prefix}-airflow-secrets-access"
  role   = aws_iam_role.airflow.id
  policy = data.aws_iam_policy_document.secrets_read.json
}
