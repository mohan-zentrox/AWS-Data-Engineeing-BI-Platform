variable "project" {
  description = "Project name used as a resource naming prefix."
  type        = string
  default     = "quarry"
}

variable "environment" {
  description = "Deployment environment name (dev, staging, prod)."
  type        = string
}

variable "use_local_dev_db" {
  description = <<-EOT
    When true (default for dev), this module provisions NO AWS resources and
    instead only emits connection settings pointing at the local
    docker-compose Postgres container (see docker-compose.yml at repo root).
    Set to false in staging/prod to provision a real RDS Postgres instance.
  EOT
  type        = bool
  default     = true
}

variable "vpc_id" {
  description = "VPC ID to launch RDS into. Required when use_local_dev_db = false."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Private subnet IDs for the RDS subnet group. Required when use_local_dev_db = false."
  type        = list(string)
  default     = []
}

variable "allowed_security_group_ids" {
  description = "Security group IDs (Glue, Airflow, metadata-api) allowed to reach Postgres on 5432."
  type        = list(string)
  default     = []
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  description = "Allocated storage in GB."
  type        = number
  default     = 20
}

variable "engine_version" {
  description = "Postgres engine version."
  type        = string
  default     = "16.3"
}

variable "database_name" {
  description = "Name of the metadata database (run state, watermarks, catalog, lineage)."
  type        = string
  default     = "quarry_metadata"
}

variable "master_username" {
  description = "Master username for the RDS instance."
  type        = string
  default     = "quarry_admin"
}

variable "manage_master_user_password" {
  description = "Let AWS manage the master password via Secrets Manager (recommended) instead of a static value."
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "Optional KMS CMK ARN for RDS storage encryption. Falls back to the AWS-managed default RDS key when null."
  type        = string
  default     = null
}

variable "backup_retention_days" {
  description = "Automated backup retention window in days."
  type        = number
  default     = 7
}

variable "multi_az" {
  description = "Enable Multi-AZ standby for the metadata DB."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Enable RDS deletion protection."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default     = {}
}
