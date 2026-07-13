output "bucket_names" {
  description = "Map of zone name -> S3 bucket name."
  value       = { for zone, bucket in aws_s3_bucket.zone : zone => bucket.bucket }
}

output "bucket_arns" {
  description = "Map of zone name -> S3 bucket ARN."
  value       = { for zone, bucket in aws_s3_bucket.zone : zone => bucket.arn }
}

output "raw_bucket_arn" {
  description = "Convenience output for the raw zone bucket ARN, used when wiring IAM policies."
  value       = try(aws_s3_bucket.zone["raw"].arn, null)
}

output "clean_bucket_arn" {
  description = "Convenience output for the clean zone bucket ARN."
  value       = try(aws_s3_bucket.zone["clean"].arn, null)
}

output "curated_bucket_arn" {
  description = "Convenience output for the curated zone bucket ARN."
  value       = try(aws_s3_bucket.zone["curated"].arn, null)
}
