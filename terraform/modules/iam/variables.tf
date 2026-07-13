variable "project" {
  description = "Project name used as a resource naming prefix."
  type        = string
  default     = "quarry"
}

variable "environment" {
  description = "Deployment environment name (dev, staging, prod)."
  type        = string
}

variable "data_lake_bucket_arns" {
  description = "ARNs of the data lake zone buckets (raw/clean/curated) that Glue and Airflow need access to."
  type        = list(string)
}

variable "kms_key_arn" {
  description = "Optional KMS CMK ARN used for SSE-KMS. When set, the roles are granted Encrypt/Decrypt/GenerateDataKey on it."
  type        = string
  default     = null
}

variable "glue_database_arns" {
  description = "ARNs of the Glue Data Catalog databases the Glue role may read/write (for the Glue crawler + jobs)."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default     = {}
}
