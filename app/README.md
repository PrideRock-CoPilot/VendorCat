# Vendor Catalog App

Databricks-compatible web application for enterprise vendor management in a parameterized Unity Catalog schema (for example, `a1_dlk.twanalytics`).

Setup assets (manual Databricks schema bootstrap, env templates, local DB bootstrap) are kept outside app runtime code under `setup/`.

## Runtime Architecture
- FastAPI web server
- Server-rendered Jinja2 templates
- Modular routers under `app/vendor_catalog_app/web/routers`
- Repository/service layer in `app/vendor_catalog_app/repository.py`
- Databricks SQL connector with local SQLite (dev) and Databricks SQL modes

## Feature Modules
- `dashboard`: executive KPIs and trends
- `vendors`: Vendor 360, offerings, ownership, docs, and audit
- `projects`: standalone project workflows, demos, notes, and mappings
- `reports`: custom reports with preview, CSV, and queued email requests
- `demos`: vendor demo outcomes
- `contracts`: contract lifecycle and cancellations
- `admin`: role grants and governance controls

## Security And Governance
- Role-aware UX (`vendor_admin`, `vendor_steward`, `vendor_editor`, `vendor_viewer`, `vendor_auditor`)
- Automatic baseline access provisioning for first-time users
- Persistent app user directory captures login identifiers and durable `user_id` references for audit/change records
- Usage telemetry events for page and action auditability
- Direct-apply vs change-request write behavior by role
- In `TVENDOR_ENV=prod`, runtime SQL policy can be enforced to allow only `INSERT`/`UPDATE` writes and block schema DDL.

## Run Modes
- Local DB mode:
```bat
set TVENDOR_ENV=dev
set TVENDOR_USE_LOCAL_DB=true
set TVENDOR_LOCAL_DB_PATH=setup\local_db\twvendor_local.db
```
- Databricks mode:
```bat
set TVENDOR_ENV=prod
set TVENDOR_USE_LOCAL_DB=false
set TVENDOR_FQ_SCHEMA=a1_dlk.twanalytics
set TVENDOR_CATALOG=a1_dlk
set TVENDOR_SCHEMA=twanalytics
set TVENDOR_ENFORCE_PROD_SQL_POLICY=true
set TVENDOR_ALLOWED_WRITE_VERBS=INSERT,UPDATE
set DATABRICKS_SERVER_HOSTNAME=<workspace-host>
set DATABRICKS_WAREHOUSE_ID=<sql-warehouse-id>
set DATABRICKS_CLIENT_ID=<service-principal-client-id>
set DATABRICKS_CLIENT_SECRET=<service-principal-client-secret>
```
PAT is still supported via `DATABRICKS_TOKEN`, but Databricks Apps should use OAuth service principal credentials.
`DATABRICKS_HTTP_PATH` is also supported directly and takes precedence when provided.

- Dev Databricks PAT mode (real Databricks data in dev):
```bat
set TVENDOR_ENV_FILE=setup\config\tvendor.dev_pat.env
launch_app.bat
```
or
```bat
launch_app_dev_pat.bat
```
Then set these values in `setup/config/tvendor.dev_pat.env`:
`DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH` (or `DATABRICKS_WAREHOUSE_ID`), and `DATABRICKS_TOKEN`.

- Databricks Apps dev fallback (no warehouse attach required):
Use `app/app.dev_local.yaml` values in your app config:
`TVENDOR_USE_LOCAL_DB=true`, `TVENDOR_LOCAL_DB_AUTO_INIT=true`, and `TVENDOR_LOCAL_DB_SEED=false`.
On startup, the app bootstraps a small local SQLite DB automatically (schema-only by default).

For Databricks Apps, prefer binding a SQL warehouse resource and use:
```yaml
- name: "DATABRICKS_WAREHOUSE_ID"
  valueFrom: "sql-warehouse"
```
The app service principal must have warehouse `CAN USE` and Unity Catalog access to the target catalog/schema/tables.

### Databricks App Identity
- The app reads Databricks forwarded identity headers (`X-Forwarded-Preferred-Username`, `X-Forwarded-Email`, `X-Forwarded-User`) per request.
- On first sign-in, users are auto-added to `app_user_directory` and auto-provisioned with lowest access (`vendor_viewer`) if no role grant exists.
- Audit/change records use the persisted `user_id` from `app_user_directory`.

`TVENDOR_USE_LOCAL_DB=true` is permitted only when `TVENDOR_ENV` is `dev`, `development`, or `local`.

For security, schema bootstrap is a manual step. The app does not create schemas/tables.

## Databricks Schema Bootstrap (Manual)
1. Configure environment values in:
```text
setup/config/tvendor.env
```
2. Render environment-specific SQL first:
```bash
python setup/databricks/render_sql.py --fq-schema a1_dlk.twanalytics
```
3. Run rendered SQL manually in Databricks SQL editor (or approved deployment pipeline):
```text
setup/databricks/rendered/001_create_databricks_schema.sql
```
4. If your schema already exists from a prior version, run:
```text
setup/databricks/rendered/002_add_offering_lob_service_type.sql
setup/databricks/rendered/003_add_lookup_scd_columns.sql
setup/databricks/rendered/004_add_offering_profile_ticket.sql
setup/databricks/rendered/005_add_offering_profile_dataflow_columns.sql
setup/databricks/rendered/006_add_offering_data_flow.sql
```
5. Start the app after bootstrap is complete.

If required tables are missing or inaccessible, startup fails with a schema/bootstrap error.

## Runtime Health Check
- API: `GET /api/health`
- Returns connection/schema readiness (`200` when healthy, `503` when bootstrap/connection is not ready).
- UI: `GET /bootstrap-diagnostics`
- HTML diagnostics page with staged checks and remediation guidance (shown automatically on schema/bootstrap failures).
- API: `GET /api/bootstrap-diagnostics`
- Returns staged diagnostics (`config`, `connectivity_probe`, runtime table/column probes) with recommendation hints.
- Use this endpoint when the UI shows `Schema Bootstrap Required` to identify whether the issue is auth/binding/UC access or missing schema objects.
- Diagnostics also include `resolved_connection` (safe previews + env-key presence map) to detect variable name mismatches.

## Local Start
1. Install dependencies:
```bash
pip install -r app/requirements.txt
```
2. Initialize local DB (optional but recommended):
```bat
python setup\local_db\init_local_db.py --reset
```
3. Launch:
```bat
launch_app.bat
```
4. Open:
```text
http://localhost:8000/dashboard
```

## Testing
```bash
python -m pytest -q tests
```

## Entry Points
- `app/main.py`
- `app/vendor_catalog_app/web/app.py`
