# Vendor Catalog

Databricks-compatible Vendor Catalog application with a complete `twvendor` data model, governed write flows, auditability, and reporting.

## What This Repo Contains
- Production-style FastAPI + Jinja web app: `app/vendor_catalog_app`
- Local SQLite bootstrap for full logical schema and seed data: `app/local_db`
- Architecture and domain design docs: `docs/architecture`
- Changelog of implemented features: `docs/CHANGELOG.md`

## Key Capabilities
- Vendor 360 with ownership, offerings, contracts, demos, lineage, and notes
- Standalone Projects workspace with linked vendors and offerings
- Document links hub (URL metadata only, no file uploads)
- Permission-aware admin and governance model
- Full audit and usage telemetry patterns
- Reports workspace with:
  - on-screen preview
  - CSV download
  - queued email extract requests

## Runtime Modes
- Mock mode (`TVENDOR_USE_MOCK=true`): in-memory test data
- Local DB mode (`TVENDOR_USE_LOCAL_DB=true`): SQLite-backed local schema
- Databricks mode: SQL warehouse + Unity Catalog schema (`<catalog>.twvendor`)

Databricks schema bootstrap is intentionally manual (security boundary). Use:
- Environment config: `app/config/tvendor.env`
- Bootstrap SQL: `app/vendor_catalog_app/sql/bootstrap/001_create_databricks_schema.sql`

## Quick Start
1. Install dependencies:
```bash
pip install -r app/requirements.txt
```
2. Start app with local DB defaults:
```bat
launch_app.bat
```
3. Open:
```text
http://localhost:8000/dashboard
```

## Database Schema
Canonical full logical schema lives at:
- `app/local_db/sql/schema/001_schema.sql`

Current schema scope:
- 40 tables
- 3 reporting views
- core, history, app workflow, security, and audit families in one logical schema (`twvendor`)

For schema details and table-by-table reference:
- `docs/database/README.md`
- `docs/database/schema-reference.md`

## Repository Structure
- `app/main.py`: app entrypoint
- `app/vendor_catalog_app/web/app.py`: FastAPI app factory
- `app/vendor_catalog_app/web/routers/`: route modules
- `app/vendor_catalog_app/repository.py`: read/write data access layer
- `app/local_db/sql/schema/`: local DDL
- `app/local_db/sql/seed/`: local seed data
- `app/local_db/sql/queries/`: reusable local SQL
- `docs/architecture/`: architecture baseline and SQL bootstrap scripts

## Validation
Run tests:
```bash
python -m pytest -q app/tests
```

## Notes
- This repo is intentionally server-rendered (no SPA rewrite).
- All write flows are permission-gated and telemetry-aware.
- In production Databricks, keep `twvendor` as the single schema boundary.
