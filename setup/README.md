# Setup Assets

This folder contains setup and bootstrap artifacts that are intentionally separate from app runtime code.

## Contents
- `config/tvendor.env`: environment template used by `launch_app.bat`.
- `databricks/render_sql.py`: renders Databricks SQL templates for a specific `<catalog>.<schema>`.
- `databricks/generate_tvendor_env.py`: generates `config/tvendor.env` for Databricks OAuth runtime (no PAT token).
- `databricks/validate_schema_and_bootstrap_admin.py`: validates schema accessibility and bootstraps admin user role grants in Databricks.
- `databricks/001_create_databricks_schema.sql`: template bootstrap script.
- `databricks/002_add_offering_lob_service_type.sql`: template migration for existing schemas.
- `databricks/003_add_lookup_scd_columns.sql`: template migration for lookup SCD validity columns.
- `local_db/`: local SQLite bootstrap scripts and schema/seed/query SQL.

## Security model
- Databricks schema bootstrap is **manual** (or pipeline-controlled).
- The app validates schema objects at startup and does not auto-create them.
