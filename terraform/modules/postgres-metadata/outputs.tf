output "host" {
  description = "Metadata DB host. Points at the docker-compose service name in dev, or the RDS endpoint otherwise."
  value       = var.use_local_dev_db ? "localhost" : try(aws_db_instance.metadata[0].address, null)
}

output "port" {
  description = "Metadata DB port."
  value       = var.use_local_dev_db ? 5432 : try(aws_db_instance.metadata[0].port, 5432)
}

output "database_name" {
  value = var.database_name
}

output "master_username" {
  value = var.master_username
}

output "is_local_dev_db" {
  value = var.use_local_dev_db
}

output "db_instance_arn" {
  description = "ARN of the RDS instance. Null when running against the local dev container."
  value       = var.use_local_dev_db ? null : try(aws_db_instance.metadata[0].arn, null)
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN holding the AWS-managed master password. Null in local dev mode."
  value       = var.use_local_dev_db ? null : try(aws_db_instance.metadata[0].master_user_secret[0].secret_arn, null)
}
