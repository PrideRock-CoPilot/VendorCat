# Vendor Catalog App

Databricks-compatible web application for enterprise vendor management in a single logical schema (`twvendor`).

## Runtime Architecture
- FastAPI web server
- Server-rendered Jinja2 templates
- Modular routers under `app/vendor_catalog_app/web/routers`
- Repository/service layer in `app/vendor_catalog_app/repository.py`
- Databricks SQL connector with mock and local SQLite fallback modes

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
- Usage telemetry events for page and action auditability
- Direct-apply vs change-request write behavior by role

## Run Modes
- Mock mode:
```bat
set TVENDOR_USE_MOCK=true
```
- Local DB mode:
```bat
set TVENDOR_USE_MOCK=false
set TVENDOR_USE_LOCAL_DB=true
set TVENDOR_LOCAL_DB_PATH=app\local_db\twvendor_local.db
```
- Databricks mode:
```bat
set TVENDOR_USE_MOCK=false
set TVENDOR_USE_LOCAL_DB=false
set DATABRICKS_SERVER_HOSTNAME=<workspace-host>
set DATABRICKS_HTTP_PATH=<sql-warehouse-http-path>
set DATABRICKS_TOKEN=<pat>
```

## Local Start
1. Install dependencies:
```bash
pip install -r app/requirements.txt
```
2. Initialize local DB (optional but recommended):
```bat
python app\local_db\init_local_db.py --reset
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
python -m pytest -q app/tests
```

## Entry Points
- `app/main.py`
- `app/vendor_catalog_app/web/app.py`
