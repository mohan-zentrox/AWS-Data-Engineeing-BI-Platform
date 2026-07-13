# Postgres Metadata module — Project Quarry
#
# Provisions the metadata store used platform-wide for pipeline run state,
# watermarks, dataset catalog, and lineage (see libs/metadata_client and
# metadata-api). Two modes:
#
#   use_local_dev_db = true (default)
#     No AWS resources are created. This lets `terraform validate` /
#     `terraform plan` succeed with zero AWS access for local development,
#     where the real Postgres instance is the docker-compose "postgres"
#     service defined at the repo root. Connection outputs point at that
#     container's default host/port/db.
#
#   use_local_dev_db = false
#     Provisions a real single-AZ (by default) RDS Postgres instance in the
#     given VPC/subnets, encrypted at rest, with AWS-managed master password
#     rotation via Secrets Manager.
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
  name_prefix = "${var.project}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Real RDS path (used when use_local_dev_db = false)
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "metadata" {
  count      = var.use_local_dev_db ? 0 : 1
  name       = "${local.name_prefix}-metadata-db-subnets"
  subnet_ids = var.subnet_ids
  tags       = merge(var.tags, { Project = var.project, Environment = var.environment })
}

resource "aws_security_group" "metadata_db" {
  count       = var.use_local_dev_db ? 0 : 1
  name        = "${local.name_prefix}-metadata-db-sg"
  description = "Allow Postgres access from Glue/Airflow/metadata-api to the Quarry metadata DB"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Project = var.project, Environment = var.environment })

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_vpc_security_group_ingress_rule" "metadata_db_from_clients" {
  for_each                    = var.use_local_dev_db ? toset([]) : toset(var.allowed_security_group_ids)
  security_group_id           = aws_security_group.metadata_db[0].id
  referenced_security_group_id = each.value
  ip_protocol                 = "tcp"
  from_port                   = 5432
  to_port                     = 5432
  description                 = "Postgres access for ${each.value}"
}

resource "aws_db_instance" "metadata" {
  count      = var.use_local_dev_db ? 0 : 1
  identifier = "${local.name_prefix}-metadata-db"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage            = var.allocated_storage_gb
  storage_encrypted            = true
  kms_key_id                   = var.kms_key_arn
  db_name                      = var.database_name
  username                     = var.master_username
  manage_master_user_password  = var.manage_master_user_password

  db_subnet_group_name   = aws_db_subnet_group.metadata[0].name
  vpc_security_group_ids = [aws_security_group.metadata_db[0].id]

  backup_retention_period = var.backup_retention_days
  multi_az                = var.multi_az
  deletion_protection     = var.deletion_protection
  skip_final_snapshot     = !var.deletion_protection
  publicly_accessible     = false
  copy_tags_to_snapshot   = true

  tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    Purpose     = "quarry-metadata-store"
  })
}
