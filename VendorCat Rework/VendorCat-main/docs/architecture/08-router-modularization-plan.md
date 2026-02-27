# Full Modularization And Codebase Overhaul Plan

## Purpose
- Establish a maintainable file structure for the entire repository, not only `vendors.py`.
- Reduce change risk by making module ownership clear and dependency flow one-directional.
- Make future feature additions predictable for new engineers.

## Current State Summary
- Router hotspots:
  - `app/vendor_catalog_app/web/routers/vendors.py` (`3964` lines)
  - `app/vendor_catalog_app/web/routers/reports.py` (`1083` lines)
  - `app/vendor_catalog_app/web/routers/workflows.py` (`935` lines)
  - `app/vendor_catalog_app/web/routers/projects.py` (`931` lines)
- Repository hotspots:
  - `app/vendor_catalog_app/repository_offering.py` (`1903` lines)
  - `app/vendor_catalog_app/repository_reporting.py` (`1384` lines)
  - `app/vendor_catalog_app/repository.py` (`997` lines)

## Architecture Principles
1. Dependency direction:
- `web (routers/templates)` -> `services` -> `repositories` -> `db/sql`
- No reverse imports.

2. Responsibility boundaries:
- Routers: HTTP parsing, auth checks, redirect/response only.
- Services: domain rules, orchestration, transactional decisions.
- Repositories: SQL execution and row/dataframe mapping only.
- SQL files: all query text and DML/DDL (no inline SQL in business code).

3. Domain-first organization:
- Vendor, Offering, Contract, Project, Demo, Workflow, Admin, Reporting each has its own module set.

4. Refactor safety:
- Preserve route paths and form contracts during split phases.
- No schema behavior changes during structural refactors.

## Target Repository Structure

```text
app/
  main.py
  requirements.txt
  app.yaml
  app.dev_local.yaml
  vendor_catalog_app/
    __init__.py

    core/
      config.py
      env.py
      logging.py
      observability.py
      security.py
      errors.py
      util.py

    db/
      client.py
      bootstrap.py
      perf.py
      cache.py

    services/
      vendor_service.py
      offering_service.py
      contract_service.py
      project_service.py
      demo_service.py
      document_service.py
      workflow_service.py
      report_service.py
      admin_service.py
      import_service.py
      user_context_service.py

    repositories/
      base.py
      vendor_repository.py
      offering_repository.py
      contract_repository.py
      project_repository.py
      demo_repository.py
      document_repository.py
      workflow_repository.py
      report_repository.py
      admin_repository.py
      lookup_repository.py
      identity_repository.py

    sql/
      bootstrap/
      health/
      ingestion/
        vendor/
        offering/
        contract/
        project/
        demo/
        workflow/
        admin/
        reporting/
      inserts/
        vendor/
        offering/
        contract/
        project/
        demo/
        workflow/
        admin/
      updates/
        vendor/
        offering/
        contract/
        project/
        demo/
        workflow/
        admin/
      local/

    web/
      app.py
      context.py
      flash.py
      errors.py
      bootstrap_diagnostics.py
      security_controls.py
      services.py

      routers/
        __init__.py
        api/
          __init__.py
          health.py
          search.py
          diagnostics.py
        dashboard/
          __init__.py
          pages.py
        vendors/
          __init__.py
          constants.py
          shared.py
          list_pages.py
          detail_pages.py
          offerings_pages.py
          offerings_writes.py
          contracts_pages.py
          contracts_writes.py
          demos_pages.py
          demos_writes.py
          projects_pages.py
          projects_writes.py
          docs_writes.py
          changes.py
        projects/
          __init__.py
          pages.py
          writes.py
          docs.py
        workflows/
          __init__.py
          pages.py
          decisions.py
        reports/
          __init__.py
          pages.py
          exports.py
          email.py
        imports/
          __init__.py
          pages.py
          preview.py
          apply.py
        admin/
          __init__.py
          pages.py
          roles.py
          scopes.py
          lookups.py
        contracts/
          __init__.py
          legacy_pages.py

      templates/
        layout/
        dashboard/
        vendors/
        projects/
        workflows/
        reports/
        imports/
        admin/
        shared/

      static/
        css/
        js/
        img/

setup/
  config/
  databricks/
  local_db/
  scripts/

deploy/
  databricks_sync/

docs/
  architecture/
  configuration/
  database/
  runbooks/
  ux/

tests/
  unit/
    services/
    repositories/
    web/
  integration/
  e2e/
  fixtures/
```

## Current-To-Target Mapping

### Core Modules
- Move:
  - `app/vendor_catalog_app/config.py` -> `app/vendor_catalog_app/core/config.py`
  - `app/vendor_catalog_app/env.py` -> `app/vendor_catalog_app/core/env.py`
  - `app/vendor_catalog_app/logging.py` -> `app/vendor_catalog_app/core/logging.py`
  - `app/vendor_catalog_app/security.py` -> `app/vendor_catalog_app/core/security.py`
  - `app/vendor_catalog_app/observability.py` -> `app/vendor_catalog_app/core/observability.py`

### Database Modules
- Move:
  - `app/vendor_catalog_app/db.py` -> `app/vendor_catalog_app/db/client.py`
  - `app/vendor_catalog_app/local_db_bootstrap.py` -> `app/vendor_catalog_app/db/bootstrap.py`
  - `app/vendor_catalog_app/cache.py` -> `app/vendor_catalog_app/db/cache.py`

### Repositories
- Split existing `repository_*.py` files into smaller domain repositories under `repositories/`.
- Keep temporary compatibility wrappers during migration:
  - old module imports delegate to new module paths until all imports are updated.

### Web Routers
- Convert each large router file into package modules by concern.
- Keep `web/routers/__init__.py` as the only include point for app startup.

### Templates
- Move templates into domain folders to match router modules.
- Keep filename aliases (or temporary include wrappers) to avoid breakage while routes migrate.

### Tests
- Reorganize tests into `unit`, `integration`, and `e2e`.
- Preserve existing tests as compatibility suite until migration is complete.

## Engineering Standards
1. File size limits:
- Router module target: <= 300 lines.
- Service module target: <= 400 lines.
- Repository module target: <= 500 lines.
- Any file > 700 lines requires explicit architecture note.

2. Function size and complexity:
- Handler function target: <= 60 lines.
- Cyclomatic complexity target: <= 12.
- Prefer helper extraction over long inline condition trees.

3. Import policy:
- Router cannot import SQL or db client directly.
- Services cannot import template/render helpers.
- Repositories cannot import web request/session objects.

4. SQL policy:
- SQL only in `sql/` files.
- Naming convention:
  - `sql/ingestion/<domain>/select_*.sql`
  - `sql/inserts/<domain>/insert_*.sql`
  - `sql/updates/<domain>/update_*.sql`

## Migration Strategy (Safe, Incremental)

### Phase 0: Baseline And Safety Net
- Generate route inventory (method/path/handler).
- Record current import graph for top modules.
- Freeze baseline performance metrics and key pages.
- Ensure core test subset is green.

### Phase 1: Introduce New Package Skeleton
- Create `core/`, `db/`, `services/`, `repositories/`, and router subpackages.
- Add compatibility re-export modules to keep old imports working.

### Phase 2: Router Decomposition
- Split `vendors.py` first, then `reports.py`, `workflows.py`, `projects.py`.
- Route behavior and paths remain unchanged.

### Phase 3: Service Extraction
- Move business logic from routers into domain services.
- Keep handlers thin and deterministic.

### Phase 4: Repository Decomposition
- Split large repositories by domain and by read/write responsibility.
- Standardize result mappers and error handling.

### Phase 5: Template Reorganization
- Move templates into domain folders.
- Update render calls, then remove temporary aliases.

### Phase 6: Test Suite Reorganization
- Move tests into layered folders with shared fixtures.
- Add architecture guard tests:
  - forbidden imports
  - file length threshold checks
  - route map consistency checks

### Phase 7: Cleanup And Hardening
- Remove compatibility wrappers.
- Remove dead modules and stale imports.
- Update onboarding docs and developer runbooks.

## Phase Exit Criteria
- Each phase must pass:
  - `tests/test_vendor_flows.py`
  - `tests/test_workflow_controls.py`
  - `tests/test_user_context.py`
  - `tests/test_reports.py`
  - `tests/test_imports_routes.py`
  - `tests/test_api_observability.py`
- Plus full `pytest` on completion of phases 3, 5, and 7.

## Ownership Model
- Assign one owner per domain package:
  - Vendor, Offering/Contract, Project/Demo, Workflow, Reporting, Admin/Identity, Platform.
- Changes crossing >2 domains require architecture review.

## Definition Of Done
- No god modules (router/repository/service files above limits).
- Clear layered dependency direction enforced by tests.
- Adding a new feature requires edits in one router module, one service module, and one repository module for that domain only.
- New engineer can locate a feature by domain folder without searching across unrelated files.
