# Lake Formation Column-Level Governance — SCAFFOLD ONLY

Reference: FRD section "Governance -> Lake Formation" and BRD section
"Compliance & Access Control".

Not implemented. This directory exists to hold Lake Formation resources once
the FRD's column-level classification (PII, financial, restricted) is
finalized against the real data dictionary.

## Intended shape

- `lake_formation_permissions.tf` (Terraform, not yet written): registers
  the curated zone S3 bucket as a Lake Formation data lake location, and
  grants column-level `SELECT` permissions per role ID (T4-LEAD, T4-DE1..3,
  T4-DATA1, T4-BE1, T4-QA1) scoped to the tables/columns each role needs —
  no wildcard grants.
- `tag_policies.tf` (not yet written): LF-Tags for data classification
  (`sensitivity = public|internal|pii|financial`) applied at the column
  level, referenced by both Lake Formation grants and the metadata catalog
  (see libs/metadata_client/schema.sql `dataset_catalog` table, which will
  gain a `sensitivity_tags` column here).
- CloudTrail + Lake Formation audit log integration for access review.

TODO(T4-LEAD, FRD 5.1 Governance): finalize column-level classification with data owners.
TODO(T4-BE1, FRD 5.1 Governance): implement lake_formation_permissions.tf against terraform/modules/s3-data-lake.
TODO(T4-DE1, FRD 5.1 Governance): extend dataset_catalog schema with sensitivity tags.
