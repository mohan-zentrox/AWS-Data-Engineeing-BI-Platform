# Lake Formation column-level permissions — SCAFFOLD ONLY, not implemented.
#
# Reference: FRD section 5.1 "Governance -> Lake Formation". See README.md
# in this directory. Left unwired from terraform/environments/dev so that
# environment's `terraform validate` does not depend on an unfinished
# classification model.
#
# TODO(T4-BE1, FRD 5.1 Governance): define aws_lakeformation_resource for the
#   curated zone bucket (terraform/modules/s3-data-lake curated_bucket_arn output).
# TODO(T4-BE1, FRD 5.1 Governance): define aws_lakeformation_permissions per
#   role ID (T4-LEAD, T4-DE1, T4-DE2, T4-DE3, T4-DATA1, T4-BE1, T4-QA1) scoped
#   to specific table columns once the data dictionary is finalized.
# TODO(T4-LEAD, FRD 5.1 Governance): review and sign off grants before apply.
