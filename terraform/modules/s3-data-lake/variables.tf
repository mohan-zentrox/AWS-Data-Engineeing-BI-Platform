variable "project" {
  description = "Project name used as a resource naming prefix (e.g. quarry)."
  type        = string
  default     = "quarry"
}

variable "environment" {
  description = "Deployment environment name (dev, staging, prod)."
  type        = string
}

variable "zones" {
  description = "Data lake zones to provision as individual S3 buckets."
  type        = list(string)
  default     = ["raw", "clean", "curated"]
}

variable "kms_key_arn" {
  description = <<-EOT
    Optional KMS CMK ARN used for SSE-KMS bucket encryption. When null, buckets
    fall back to SSE-S3 (AES256) so the module can be validated/applied in
    accounts without a pre-provisioned CMK. Pass a real CMK ARN in prod.
  EOT
  type        = string
  default     = null
}

variable "force_destroy" {
  description = "Allow buckets to be destroyed even if they still contain objects. Should be false in prod."
  type        = bool
  default     = false
}

variable "noncurrent_version_expiration_days" {
  description = "Days after which noncurrent object versions are expired."
  type        = number
  default     = 90
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default     = {}
}
