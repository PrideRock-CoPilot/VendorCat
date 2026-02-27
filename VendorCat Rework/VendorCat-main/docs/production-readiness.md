# Production Readiness Checklist

Use this checklist before promoting Vendor Catalog to Databricks production.

## 1. Schema Bootstrap (Manual, Required)
- Render SQL for your target schema, for example:
  - `python setup/databricks/render_sql.py --fq-schema a1_dlk.twanalytics`
- Run `setup/databricks/rendered/001_create_databricks_schema.sql`
- For existing deployments, also run:
  - `setup/databricks/rendered/002_add_offering_lob_service_type.sql`
  - `setup/databricks/rendered/003_add_lookup_scd_columns.sql`
  - `setup/databricks/rendered/004_add_offering_profile_ticket.sql`
  - `setup/databricks/rendered/005_add_offering_profile_dataflow_columns.sql`
  - `setup/databricks/rendered/006_add_offering_data_flow.sql`

## 2. Databricks App Runtime Config
- `TVENDOR_ENV=prod`
- `TVENDOR_USE_LOCAL_DB=false`
- `TVENDOR_FQ_SCHEMA=<catalog>.<schema>` (preferred)
  - or set both `TVENDOR_CATALOG=<catalog>` and `TVENDOR_SCHEMA=<schema>`
- `DATABRICKS_SERVER_HOSTNAME=<workspace-hostname>` (or rely on platform `DATABRICKS_HOST`)
- `DATABRICKS_HTTP_PATH=<sql-warehouse-http-path>` or `DATABRICKS_WAREHOUSE_ID=<warehouse-id>`
- `TVENDOR_ENFORCE_PROD_SQL_POLICY=true`
- `TVENDOR_ALLOWED_WRITE_VERBS=INSERT,UPDATE`
- Authentication:
  - Preferred: `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`
  - Fallback: `DATABRICKS_TOKEN`

## 3. Permissions
- App principal can `SELECT` all required runtime tables.
- App principal can `INSERT/UPDATE`:
  - `app_user_directory`
  - `sec_user_role_map`
  - app workflow/audit tables used by your selected features.

## 4. Identity + Access Behavior Validation
- Confirm Databricks forwarded identity headers are available:
  - `X-Forwarded-Preferred-Username` or `X-Forwarded-Email`
- First-time user should be auto-created in `app_user_directory`.
- User with no explicit role should get lowest access (`vendor_viewer`).

## 5. Runtime Health Validation
- Call `GET /api/health`
- Expected:
  - `200` with `"ok": true` when ready
  - `503` with clear bootstrap/connection detail when not ready

## 6. Quality Gate
- Run `python -m pytest -q tests`
- Ensure all tests pass before deployment.
