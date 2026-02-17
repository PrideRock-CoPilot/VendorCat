# Vendor Catalog

Databricks-compatible Vendor Catalog application with a complete data model, governed write flows, auditability, and reporting across parameterized Unity Catalog schemas.

## What This Repo Contains
- Production-style FastAPI + Jinja web app: `app/vendor_catalog_app`
- Local SQLite bootstrap for full logical schema and seed data: `setup/local_db`
- Architecture and domain design docs: `docs/architecture`
- Governance and drift prevention framework: `docs/governance`
- Operational runbooks: `docs/operations`
- Changelog of implemented features: `docs/CHANGELOG.md`

## Documentation

**Start here**: [Documentation Index](docs/README.md)

**Essential reads for developers**:
- [Guardrails](docs/governance/guardrails.md) - 10 non-negotiable rules
- [Definition of Done](docs/governance/definition-of-done.md) - PR checklists
- [RBAC & Permissions](docs/architecture/rbac-and-permissions.md) - Permission enforcement patterns
- [CI Quality Gates](docs/operations/ci-quality-gates.md) - Running checks locally

**For deployments**:
- [Release Process](docs/governance/release-process.md) - Branch strategy, versioning, rollback
- [Migrations & Schema](docs/operations/migrations-and-schema.md) - Schema change workflow

**For drift prevention**:
- [Drift Threat Model](docs/governance/drift-threat-model.md) - Top 10 drift vectors with SLO targets
- [PR Bundles](docs/roadmap/pr-bundles.md) - Step-by-step implementation plan

## Top-Level Layout
- `app/`: runtime application code only
- `docs/`: architecture and product documentation
- `tests/`: automated test suite
- `setup/`: environment templates and manual bootstrap assets

## Key Capabilities
- Vendor 360 with ownership, offerings, contracts, demos, lineage, and notes
- Standalone Projects workspace with linked vendors and offerings
- Document links hub (URL metadata only, no file uploads)
- Permission-aware admin and governance model
- Full audit and usage telemetry patterns
- Persistent user directory (`app_user_directory`) so audit trails retain identity even after AD/account churn
- Reports workspace with:
  - on-screen preview
  - CSV download
  - queued email extract requests

## Runtime Modes
- Local DB mode (`TVENDOR_ENV=dev` + `TVENDOR_USE_LOCAL_DB=true`): SQLite-backed local schema
- Databricks mode: SQL warehouse + Unity Catalog schema (`<catalog>.<schema>`, example `a1_dlk.twanalytics`)
  - Auth supports either PAT (`DATABRICKS_TOKEN`) or OAuth service principal (`DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`) for Databricks Apps.
  - User identity is sourced from Databricks forwarded headers and persisted to `app_user_directory` on first access.
  - HTTP path can be provided directly (`DATABRICKS_HTTP_PATH`) or derived from `DATABRICKS_WAREHOUSE_ID`.
  - Prod SQL policy can be enforced with `TVENDOR_ENFORCE_PROD_SQL_POLICY=true` and `TVENDOR_ALLOWED_WRITE_VERBS=INSERT,UPDATE`.

Configuration reference:
- `docs/configuration/environment-variables.md`

Safety guard: local DB is enabled only for `TVENDOR_ENV` values `dev`, `development`, or `local`.

Databricks schema bootstrap is intentionally manual (security boundary). Use:
- Environment config: `setup/config/tvendor.env`
- Render SQL for your target schema: `python setup/databricks/render_sql.py --fq-schema a1_dlk.twanalytics`
- Bootstrap SQL: `setup/databricks/rendered/001_create_databricks_schema.sql`
- Existing-schema migration (LOB/Service Type columns): `setup/databricks/rendered/002_add_offering_lob_service_type.sql`
- Existing-schema migration (lookup SCD validity columns): `setup/databricks/rendered/003_add_lookup_scd_columns.sql`
- Existing-schema migration (offering profile + ticket tables): `setup/databricks/rendered/004_add_offering_profile_ticket.sql`
- Existing-schema migration (offering profile dataflow columns): `setup/databricks/rendered/005_add_offering_profile_dataflow_columns.sql`
- Existing-schema migration (offering data flow table): `setup/databricks/rendered/006_add_offering_data_flow.sql`

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
- `setup/local_db/sql/schema/001_schema.sql`

Current schema scope:
- 41 tables
- 3 reporting views
- core, history, app workflow, security, and audit families in one logical schema (`twvendor`)

For schema details and table-by-table reference:
- `docs/database/README.md`
- `docs/database/schema-reference.md`
- `docs/user-guide.md`
- `docs/ux/click-budget.md`
- `docs/ux/screen-audit.md`
- `docs/ux/prioritized-backlog.md`

## Repository Structure
- `app/main.py`: app entrypoint
- `app/vendor_catalog_app/web/app.py`: FastAPI app factory
- `app/vendor_catalog_app/web/routers/`: route modules
- `app/vendor_catalog_app/repository.py`: read/write data access layer
- `setup/local_db/sql/schema/`: local DDL
- `setup/local_db/sql/seed/`: local seed data
- `setup/local_db/sql/queries/`: reusable local SQL
- `docs/architecture/`: architecture baseline and SQL bootstrap scripts

## Validation
Run tests:
```bash
python -m pytest -q tests
```

Health endpoint:
```text
/api/health
```

Production checklist:
```text
docs/production-readiness.md
```

## Notes
- This repo is intentionally server-rendered (no SPA rewrite).
- All write flows are permission-gated and telemetry-aware.
- In production Databricks, set schema by environment variables (`TVENDOR_FQ_SCHEMA` or `TVENDOR_CATALOG` + `TVENDOR_SCHEMA`).
- In production Databricks, enable runtime SQL policy to block DDL and allow only approved write verbs.
