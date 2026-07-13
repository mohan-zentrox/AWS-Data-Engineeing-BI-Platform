output "glue_role_arn" {
  description = "ARN of the least-privilege IAM role assumed by AWS Glue jobs/crawlers."
  value       = aws_iam_role.glue.arn
}

output "glue_role_name" {
  value = aws_iam_role.glue.name
}

output "airflow_role_arn" {
  description = "ARN of the least-privilege IAM role assumed by Airflow (MWAA or self-managed)."
  value       = aws_iam_role.airflow.arn
}

output "airflow_role_name" {
  value = aws_iam_role.airflow.name
}
