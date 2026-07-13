output "data_lake_bucket_names" {
  value = module.s3_data_lake.bucket_names
}

output "glue_role_arn" {
  value = module.iam.glue_role_arn
}

output "airflow_role_arn" {
  value = module.iam.airflow_role_arn
}

output "metadata_db_host" {
  value = module.postgres_metadata.host
}

output "metadata_db_is_local_dev" {
  value = module.postgres_metadata.is_local_dev_db
}
