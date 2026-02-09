# Databricks SQL Bootstrap Scripts

These scripts provide a Databricks-oriented bootstrap path for the `twvendor` model.

## Script Order
1. `01_uc_bootstrap.sql`
2. `02_core_tables.sql`
3. `03_security_views.sql`

## Coverage
- Source landing tables (`src_`)
- Canonical entities (`core_`)
- History (`hist_`)
- Audit (`audit_`)
- Workflow tables (`app_`) including projects and document links
- Security tables (`sec_`)
- Serving/reporting views (`rpt_`)

## Notes
- This folder is the Databricks bootstrap view of the model.
- Canonical full local logical schema (with indexes and local constraints) is:
  - `app/local_db/sql/schema/001_schema.sql`
