# Rebuild Implementation Status

## As Of 2026-02-20

## Completed
- Phase 0 foundation:
  - Rebuild branch established (`rebuild/django5-full-parity`)
  - Baseline freeze artifacts committed under `docs/rebuild/phase0/`
  - Legacy root artifacts moved to `archive/legacy-dev-artifacts/`
- Phase 1 platform bootstrap:
  - Django 5 project scaffold under `src/`
  - App matrix created (`core`, `identity`, `admin_portal`, `vendors`, `offerings`, `projects`, `imports`, `workflows`, `reports`, `help_center`, `contracts`, `demos`)
  - Top-level continuity routes active (`/dashboard`, `/vendor-360`, `/projects`, `/imports`, `/workflows`, `/reports`, `/admin`)
  - HTMX-enabled shared base template and section placeholders
  - Runtime matrix parsing for local and Databricks profiles
  - Request ID, structured request logging, unified error middleware, health/live/ready/runtime endpoints
- Phase 2 bootstrap:
  - Canonical `vc_*` schema bundle under `src/schema/canonical/`
  - Rendered DuckDB + Databricks schema bundles under `src/schema/rendered/`
  - SQL adapter layer with DuckDB implementation + Databricks connector baseline
  - Clean rebuild runner (`scripts/runtime/run_clean_rebuild.ps1`)
  - Schema quality validator (`scripts/runtime/validate_schema.py`)
  - SQL coverage validator (`scripts/runtime/validate_sql_coverage.py`)

## Quality Gate Status (Rebuild Scope)
- `ruff check src tests_rebuild`: passing
- `mypy --config-file mypy-rebuild.ini src tests_rebuild`: passing
- Rebuild tests (`tests_rebuild`): 38 passing
- Rebuild coverage gate: 81.23% (threshold 80%)
- Rebuild CI workflow: strict (no `continue-on-error`)

## In Progress / Pending
- Phase 3:
  - Initial API slice complete:
    - User directory persistence wired into identity/access endpoints
    - Access request workflow endpoint with policy enforcement (`/api/v1/access/requests`)
    - Terms acceptance endpoint with idempotent persistence (`/api/v1/access/terms/accept`)
    - First-admin bootstrap endpoint with one-time guard (`/api/v1/access/bootstrap-first-admin`)
    - Rebuild coverage expanded with `tests_rebuild/test_access_workflows_rebuild.py`
    - Access-request submission and review flow complete:
      - Request submission UI/API (`/access/requests`, `/api/v1/access/requests`)
      - Reviewer queue and decision UI/API (`/access/requests/review`, `/api/v1/access/requests/list`, `/api/v1/access/requests/{id}/review`)
      - Approval grants requested role assignment to requestor
    - Route-to-permission enforcement expansion complete across mapped mutation handlers (vendor/project/import/workflow/report endpoints)
- Phase 4:
  - **COMPLETE**: Vendor/offering/project/contract/demo parity w/ full CRUD + validation + permissions + UI
  - Vendor CRUD API (create/list/detail/update) with lifecycle/risk validation (2/2 tests passing)
  - Project CRUD API (create/list/detail/update) with lifecycle validation (2/2 tests passing)
  - Offering CRUD API (create/list/detail/update) with lifecycle/type/LOB validation + UI pages (4/4 tests passing)
  - Contract CRUD API (create/list/detail/update) with status/date/decimal validation + UI pages (4/4 tests passing)
  - Demo CRUD API (create/list/detail/update) with lifecycle/type/outcome validation + UI pages (4/4 tests passing)
  - Permission mappings for vendor.write, project.write, offering.write, contract.write, demo.write
  - Schema tables for all 5 entities (vc_vendor, vc_offering, vc_project, vc_contract, vc_demo)
  - Navigation context updated to include /offerings, /contracts, /demos
  - Rebuild test coverage: 17 Phase 4 tests (all passing)
- Phase 5:
  - **COMPLETE**: Imports/workflows parity w/ full CRUD + validation + permissions + UI
  - Import job CRUD API (create/list/detail/update) with status/format validation + UI pages (4/4 tests passing)
  - Mapping profile model for source-to-target field mappings
  - Workflow decision CRUD API (create/list/detail/update) with status validation + UI pages (4/4 tests passing)
  - Permission mappings for import.run and workflow.run
  - Schema tables for all 3 entities (vc_import_job, vc_mapping_profile, vc_workflow_decision)
  - Navigation routes for /imports and /workflows (trailing slash)
  - Rebuild test coverage: 8 Phase 5 tests (all passing)
- Phase 6:
  - Reports/help-center parity and observability/perf baselines
- Phase 7:
  - Expand strict gates from rebuild scope to full branch parity suites
- Phase 8:
  - Cutover/decommission playbooks and smoke certification

