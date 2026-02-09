# Vendor Catalog App

Databricks-compatible Vendor Catalog web application built with FastAPI and Jinja templates.

## Stack
- FastAPI web server
- Server-rendered HTML templates (Jinja2)
- Modular route handlers (`dashboard`, `vendors`, `demos`, `contracts`, `admin`)
- Python repository layer + Databricks SQL connector
- Unity Catalog schema: `vendor_<env>.twvendor`

## Why This Structure
- No Streamlit dependency.
- Split into focused modules instead of monolithic UI files.
- Works in locked-down environments with standard Python web runtime.

## App Modules
- Dashboard: executive insights and spend/risk/renewal summaries.
- Vendor 360: filtered list, row-click detail navigation, settings-driven field matrix.
- Vendor detail: ownership, portfolio, contracts, demos, lineage, change requests, audit timeline.
- Demos: outcome capture.
- Contracts: cancellation capture.
- Admin: role/scope grants.

## Governance Features
- Auto-provision first-time users with `vendor_viewer` rights.
- Persist per-user Vendor 360 field settings.
- Usage telemetry (`session_start`, `page_view`, and key interactions).
- Audited direct profile updates for admin/steward roles.

## Run Locally
1. Install dependencies:
```bash
pip install -r app/requirements.txt
```
2. Set env vars using `app/.env.example`.
3. Start:
```bash
python -m uvicorn --app-dir app main:app --host 0.0.0.0 --port 8000
```
4. Open `http://localhost:8000/dashboard`.

## Entry Points
- App server: `app/main.py`
- FastAPI factory: `app/vendor_catalog_app/web/app.py`
- Routers: `app/vendor_catalog_app/web/routers/`
