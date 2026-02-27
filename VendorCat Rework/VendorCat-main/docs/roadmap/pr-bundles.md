# PR Bundle Execution Plan

This document breaks down drift elimination into sequential Pull Requests with clear acceptance criteria.

## Overview

**Goal**: Eliminate top drift vectors over 5-8 PRs

**Timeline**: 6-8 weeks (1 PR per week)

**Branch**: All PRs from `main` to `main`

**Dependencies**: PRs should be done in order (some have dependencies)

## PR Bundle 1: CI/CD Foundation

**Addresses Drift**: DRIFT-010 (test coverage), DRIFT-001 (RBAC), DRIFT-007 (SQL in routers)

**Description**: Set up CI pipeline with automated quality gates

**Files Created/Modified**:
- `.github/workflows/ci.yml` (new)
- `.github/pull_request_template.md` (new)
- `.github/CODEOWNERS` (new)
- `pyproject.toml` (new)
- `.ruff.toml` (new)
- `README.md` (update with CI badge)

**Tasks**:
1. Create CI workflow with pytest, ruff, mypy, coverage checks
2. Configure coverage threshold (80%)
3. Create PR template with DoD checklists
4. Create CODEOWNERS file (Tech Lead)
5. Configure linter rules (detect SQL in routers)
6. Configure type checker (mypy)

**Acceptance Criteria**:
- [ ] CI runs on every push and PR
- [ ] All existing tests pass in CI
- [ ] Coverage report generated (may be below 80% initially)
- [ ] Ruff linting passes (or creates TODO issues for violations)
- [ ] MyPy type checking passes (allow existing errors with baseline)
- [ ] PR template appears on new PRs
- [ ] CODEOWNERS assigned for reviews

**Rollback**: Delete `.github/workflows/ci.yml` to disable CI

**Estimated Effort**: 8-12 hours

**Dependencies**: None

---

## PR Bundle 2: RBAC Enforcement Infrastructure

**Addresses Drift**: DRIFT-001 (permission bypass)

**Description**: Create RBAC decorator and coverage test to enforce permission checks

**Files Created/Modified**:
- `app/vendor_catalog_app/web/security/__init__.py` (new)
- `app/vendor_catalog_app/web/security/rbac.py` (new)
- `app/vendor_catalog_app/core/permissions.py` (new)
- `tests/test_rbac_coverage.py` (new)
- `docs/architecture/rbac-and-permissions.md` (update with examples)

**Tasks**:
1. Create `@require_permission` decorator
2. Define ROLE_PERMISSIONS mapping (roles → change types)
3. Create test_rbac_coverage.py to scan routers
4. Apply decorator to 3-5 endpoints as examples
5. Document usage pattern

**Acceptance Criteria**:
- [ ] `@require_permission` decorator implemented
- [ ] Decorator blocks unauthorized access (returns 403)
- [ ] test_rbac_coverage.py scans all routers
- [ ] Test identifies missing permission checks
- [ ] Test passes for decorated endpoints
- [ ] Test fails for undecorated endpoints (expected - will fix in PR 3)
- [ ] CI runs RBAC coverage test (allowed to fail for now)

**Rollback**: Remove decorator, delete test (does not break existing functionality)

**Estimated Effort**: 12-16 hours

**Dependencies**: PR 1 (needs CI to run test)

---

## PR Bundle 3: RBAC Rollout to All Endpoints

**Addresses Drift**: DRIFT-001 (permission bypass)

**Description**: Apply `@require_permission` to all mutation endpoints

**Files Modified**:
- All router files in `app/vendor_catalog_app/web/routers/`
- May need to refactor some endpoints to support decorator

**Tasks**:
1. Scan routers for POST/PUT/PATCH/DELETE without permission check
2. Add `@require_permission` decorator to each
3. Verify appropriate change_type for each endpoint
4. Add tests for unauthorized access (403 response)
5. Update existing tests to include authenticated user

**Acceptance Criteria**:
- [ ] All mutation endpoints have `@require_permission` or inline check
- [ ] test_rbac_coverage.py passes (0 violations)
- [ ] CI blocks PRs if RBAC coverage test fails
- [ ] All tests pass with permission checks enforced
- [ ] Manual smoke test: unauthorized user gets 403

**Rollback**: Revert router changes, decorator remains but not enforced

**Estimated Effort**: 16-24 hours (depends on number of violations)

**Dependencies**: PR 2 (needs decorator)

---

## PR Bundle 4: Schema Migration Framework

**Addresses Drift**: DRIFT-002 (schema changes without migrations)

**Description**: Implement migration runner and version tracking

**Files Created/Modified**:
- `app/vendor_catalog_app/infrastructure/migrations.py` (new)
- `setup/databricks/migration_007_create_schema_version_table.sql` (new)
- `app/main.py` (add startup schema version check)
- `docs/operations/migrations-and-schema.md` (update with examples)

**Tasks**:
1. Create `app_schema_version` table
2. Implement migration runner (`apply_migration`, `rollback_migration`)
3. Add schema version check to app startup
4. Document migration file template
5. Create example migration (007_schema_version_table)

**Acceptance Criteria**:
- [ ] `app_schema_version` table exists
- [ ] Migration runner can apply migration files
- [ ] App startup fails if schema version < expected version
- [ ] Example migration applied successfully
- [ ] Documentation updated with migration workflow

**Rollback**: Drop app_schema_version table, remove startup check

**Estimated Effort**: 10-14 hours

**Dependencies**: None

---

## PR Bundle 5: Audit Trail Completeness

**Addresses Drift**: DRIFT-003 (audit trail gaps)

**Description**: Ensure all mutations write audit records

**Files Modified**:
- Repository files in `app/vendor_catalog_app/backend/repository_mixins/`
- Add `_write_audit_entity_change` calls to missing methods

**Tasks**:
1. Audit all repository write methods (create, update, delete)
2. Add `_write_audit_entity_change` to methods missing it
3. Include before/after snapshots
4. Add correlation ID to audit records
5. Create test to verify audit completeness (sample spot check)

**Acceptance Criteria**:
- [ ] All create/update/delete methods call audit write
- [ ] Before/after snapshots included
- [ ] Correlation ID tracked
- [ ] Spot check test passes (create vendor → audit record exists)
- [ ] No mutations skipped

**Rollback**: Revert audit calls (non-breaking, just missing audit)

**Estimated Effort**: 12-18 hours

**Dependencies**: None

---

## PR Bundle 6: Input Validation and Sanitization

**Addresses Drift**: DRIFT-004 (input validation), DRIFT-008 (XSS)

**Description**: Standardize input validation using Pydantic models and sanitize HTML

**Files Created/Modified**:
- `app/vendor_catalog_app/web/models/` (new directory)
- `app/vendor_catalog_app/web/models/vendor_forms.py` (new)
- `app/vendor_catalog_app/web/utils/validation.py` (new)
- `app/vendor_catalog_app/web/utils/sanitization.py` (new)
- Router files updated to use Pydantic models
- `requirements.txt` (add bleach for HTML sanitization)

**Tasks**:
1. Create Pydantic models for form inputs (VendorForm, ContactForm, etc.)
2. Implement validation helpers (validate_url, validate_email)
3. Implement HTML sanitization (bleach.clean)
4. Update routers to use Pydantic form models
5. Sanitize user HTML content before storage
6. Audit templates for `| safe` usage, verify sanitization

**Acceptance Criteria**:
- [ ] Pydantic models defined for all forms
- [ ] Form inputs validated automatically
- [ ] Invalid inputs return 400 with error message
- [ ] HTML content sanitized at write time
- [ ] All `| safe` usage audited and documented
- [ ] XSS test fails (injection attempt blocked)

**Rollback**: Revert to old validation (non-breaking if Pydantic models match old behavior)

**Estimated Effort**: 16-20 hours

**Dependencies**: None

---

## PR Bundle 7: Data Ownership and Override Flags

**Addresses Drift**: DRIFT-006 (ingestion vs app conflicts)

**Description**: Implement user override mechanism for ingestion-owned fields

**Files Created/Modified**:
- `setup/databricks/migration_008_add_override_flags.sql` (new)
- Ingestion merge logic in pipeline (if exists) or placeholder
- Vendor edit UI (add override checkboxes)
- Repository methods updated to respect override flags

**Tasks**:
1. Create migration to add user_override_* columns
2. Update vendor edit form to include override checkboxes
3. Update repository to set override flags when user edits
4. Update ingestion merge logic to skip fields with override flag
5. Add UI indicator (icon) for overridden fields
6. Document ownership matrix

**Acceptance Criteria**:
- [ ] Override flag columns exist
- [ ] User edit sets override flag
- [ ] Ingestion respects override flag (skips field)
- [ ] UI shows override indicator
- [ ] User can clear override (revert to ingestion)
- [ ] Documentation complete

**Rollback**: Drop override columns, remove UI elements

**Estimated Effort**: 14-18 hours

**Dependencies**: PR 4 (needs migration framework)

---

## PR Bundle 8: Observability and Monitoring

**Addresses Drift**: DRIFT-009 (metric/logging inconsistency)

**Description**: Standardize logging and metrics across application

**Files Created/Modified**:
- `app/vendor_catalog_app/infrastructure/observability.py` (new)
- `app/main.py` (add metrics endpoint)
- Router files (add logging and metrics)
- `requirements.txt` (add prometheus-client)

**Tasks**:
1. Implement structured logging helper
2. Implement Prometheus metrics (counters, histograms)
3. Add correlation ID middleware
4. Add metrics to key endpoints (vendor create, search)
5. Add INFO logs for business events
6. Add ERROR logs with context
7. Create `/metrics` endpoint

**Acceptance Criteria**:
- [ ] Structured logging implemented
- [ ] Correlation IDs in all logs
- [ ] Metrics emitted for key flows
- [ ] `/metrics` endpoint returns Prometheus format
- [ ] Business events logged (vendor create, update, delete)
- [ ] Errors logged with context and stack traces

**Rollback**: Remove observability code (non-breaking)

**Estimated Effort**: 12-16 hours

**Dependencies**: None

---

## Optional PR Bundle 9: Foreign Key Validation

**Addresses Drift**: DRIFT-005 (orphaned records)

**Description**: Add FK validation before insert

**Files Modified**:
- Repository methods (add FK existence checks)
- Create helper methods (`_ensure_vendor_exists`, etc.)

**Tasks**:
1. Create FK validation helpers
2. Add FK checks to all insert methods
3. Add data quality check SQL (find orphans)
4. Run one-time cleanup of existing orphans

**Acceptance Criteria**:
- [ ] FK validation in all insert methods
- [ ] Invalid FK raises ValueError
- [ ] Data quality check finds 0 orphans
- [ ] Tests verify FK validation

**Rollback**: Remove FK checks (non-breaking, just allows bad data)

**Estimated Effort**: 8-12 hours

**Dependencies**: None

---

## Progress Tracking

Use this table to track progress:

| PR # | Title | Status | PR Link | Merged Date |
|------|-------|--------|---------|-------------|
| 1 | CI/CD Foundation | Not Started | | |
| 2 | RBAC Enforcement Infrastructure | Not Started | | |
| 3 | RBAC Rollout to All Endpoints | Not Started | | |
| 4 | Schema Migration Framework | Not Started | | |
| 5 | Audit Trail Completeness | Not Started | | |
| 6 | Input Validation and Sanitization | Not Started | | |
| 7 | Data Ownership and Override Flags | Not Started | | |
| 8 | Observability and Monitoring | Not Started | | |
| 9 | Foreign Key Validation (Optional) | Not Started | | |

## Drift Mapping

Each PR addresses specific drift vectors:

| Drift Vector | PR # | Status |
|--------------|------|--------|
| DRIFT-001: Permission bypass | PR 2, PR 3 | Not Started |
| DRIFT-002: Schema changes without migrations | PR 4 | Not Started |
| DRIFT-003: Audit trail gaps | PR 5 | Not Started |
| DRIFT-004: Input validation inconsistency | PR 6 | Not Started |
| DRIFT-005: Foreign key orphans | PR 9 | Not Started |
| DRIFT-006: Ingestion vs app edit conflicts | PR 7 | Not Started |
| DRIFT-007: Raw SQL in routers | PR 1 (lint) | Not Started |
| DRIFT-008: Template XSS via \|safe | PR 6 | Not Started |
| DRIFT-009: Metric/logging inconsistency | PR 8 | Not Started |
| DRIFT-010: Test coverage decay | PR 1 (CI) | Not Started |

---

Last updated: 2026-02-15
