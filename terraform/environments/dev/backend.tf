# Remote state backend for the dev environment.
#
# Left commented out on purpose: the CI pipeline and local module validation
# run `terraform init -backend=false` (see .github/workflows/ci.yml), which
# does not require this block. Uncomment and fill in a real bucket/table
# before the first real `terraform apply` against AWS, then run
# `terraform init -migrate-state` once.
#
# terraform {
#   backend "s3" {
#     bucket         = "quarry-dev-tfstate"
#     key            = "environments/dev/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "quarry-dev-tfstate-lock"
#     encrypt        = true
#   }
# }
