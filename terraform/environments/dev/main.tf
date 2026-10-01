# Project Quarry — dev environment root module
#
# Wires the three reusable modules together for the "dev" environment.
# Run `terraform init -backend=false` to validate module wiring locally
# without AWS credentials or a configured remote backend (see backend.tf).
#
# Apply requires real AWS credentials for account/region set via
# AWS_PROFILE / AWS_REGION env vars or terraform.tfvars — see
# terraform.tfvars.example.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "project-quarry"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "s3_data_lake" {
  source = "../../modules/s3-data-lake"

  project       = var.project
  environment   = var.environment
  zones         = ["raw", "clean", "curated"]
  kms_key_arn   = var.kms_key_arn
  force_destroy = var.dev_force_destroy
}

module "iam" {
  source = "../../modules/iam"

  project     = var.project
  environment = var.environment
  kms_key_arn = var.kms_key_arn

  data_lake_bucket_arns = [
    module.s3_data_lake.raw_bucket_arn,
    module.s3_data_lake.clean_bucket_arn,
    module.s3_data_lake.curated_bucket_arn,
  ]
}

module "postgres_metadata" {
  source = "../../modules/postgres-metadata"

  project          = var.project
  environment      = var.environment
  use_local_dev_db = var.use_local_dev_db
  database_name    = var.metadata_db_name
}
