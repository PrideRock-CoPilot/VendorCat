# Setup Assets

This folder contains setup and bootstrap artifacts that are intentionally separate from app runtime code.

## Contents
- `config/tvendor.env`: environment template used by `launch_app.bat`.
- `databricks/001_create_databricks_schema.sql`: manual Databricks schema bootstrap script.
- `databricks/002_add_offering_lob_service_type.sql`: manual migration for existing schemas.
- `databricks/003_add_lookup_scd_columns.sql`: manual migration for lookup SCD validity columns.
- `local_db/`: local SQLite bootstrap scripts and schema/seed/query SQL.

## Security model
- Databricks schema bootstrap is **manual** (or pipeline-controlled).
- The app validates schema objects at startup and does not auto-create them.
