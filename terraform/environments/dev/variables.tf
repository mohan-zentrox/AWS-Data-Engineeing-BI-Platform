variable "project" {
  description = "Project name used as a resource naming prefix."
  type        = string
  default     = "quarry"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "kms_key_arn" {
  description = "Optional KMS CMK ARN for SSE-KMS on S3 and RDS storage encryption. Leave null to use AWS-managed keys in dev."
  type        = string
  default     = null
}

variable "dev_force_destroy" {
  description = "Allow dev S3 buckets to be destroyed even with objects present. Keep true only in dev."
  type        = bool
  default     = true
}

variable "use_local_dev_db" {
  description = "When true, the postgres-metadata module provisions no AWS resources and dev points at docker-compose Postgres instead."
  type        = bool
  default     = true
}

variable "metadata_db_name" {
  description = "Name of the metadata database."
  type        = string
  default     = "quarry_metadata"
}
