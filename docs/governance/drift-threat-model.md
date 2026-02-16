# Drift Threat Model

Drift is divergence from agreed standards, patterns, or rules that accumulates over time and erodes system quality.

This document defines drift vectors for VendorCatalog, how to prevent them, how to detect them, and who owns remediation.

## Drift Service Level Objectives (SLOs)

| Metric | Target | Measurement | Owner |
|--------|--------|-------------|-------|
| RBAC coverage on mutation endpoints | 100% | CI test: test_rbac_coverage.py | Tech Lead |
| Migration tracking | 100% | All schema changes have migration_NNN.sql | Data Lead |
| Audit completeness | 100% | All mutations call _write_audit_entity_change | Tech Lead |
| Input validation on public fields | 100% | All form inputs validated (length, format, type) | Tech Lead |
| Foreign key validation before insert | 100% | No orphaned records | Data Lead |
| Test coverage | >=80% | pytest --cov | Tech Lead |
| Security vulnerability age | <7 days | Dependabot alerts addressed | Security Lead |
| Documentation staleness | <30 days | Last update timestamp in docs | Tech Lead |

## Top 10 Drift Vectors

### DRIFT-001: Permission Bypass Vulnerabilities

**Severity**: Critical

**Description**: Mutation endpoints (POST/PUT/PATCH/DELETE) added without permission checks allow unauthorized data modification.

**Prevention**:
- Use `@require_permission(change_type)` decorator on all mutation endpoints
- Pattern: `if not user.can_apply_change(change_type): raise HTTPException(403)`
- See: [RBAC & Permissions](../architecture/rbac-and-permissions.md)

**Detection**:
- CI test: `test_rbac_coverage.py` scans all router files for mutation decorators and verifies permission check exists
- Manual: Grep for `@router.post` and verify adjacent permission check

**Remediation**:
- Add missing permission checks following pattern in [rbac.py](../../app/vendor_catalog_app/web/security/rbac.py)
- Add test case for unauthorized access attempt

**Owner**: Tech Lead

**Evidence File**: `tests/test_rbac_coverage.py`

---

### DRIFT-002: Schema Changes Without Migrations

**Severity**: Critical

**Description**: Database schema altered without tracked migration file causes deployment failures and schema version drift across environments.

**Prevention**:
- All DDL changes require `setup/databricks/migration_NNN_description.sql` file
- Migration number must increment sequentially
- Record in `app_schema_version` table on apply
- See: [Migrations & Schema](../operations/migrations-and-schema.md)

**Detection**:
- CI check: Verify no SQL files modified without corresponding migration file (future enhancement)
- Manual: Check `app_schema_version` across dev/staging/prod for version drift

**Remediation**:
- Create retroactive migration file for undocumented schema change
- Apply to all environments in correct order
- Add version check to startup validation

**Owner**: Data Lead

**Evidence File**: `app/vendor_catalog_app/infrastructure/migrations.py`

---

### DRIFT-003: Audit Trail Gaps

**Severity**: High

**Description**: Mutations that don't log to `audit_entity_change` create compliance gaps and debugging blind spots.

**Prevention**:
- All repository write methods must call `_write_audit_entity_change(...)`
- Pattern established in `app/vendor_catalog_app/backend/repository_mixins/common/core/audit.py`
- Include before/after snapshots, actor identity, request ID

**Detection**:
- Code review: Check new repository methods for audit call
- Manual audit: Query `audit_entity_change` for entity and verify mutation coverage

**Remediation**:
- Add missing audit calls to non-compliant methods
- Backfill audit records if historical data available

**Owner**: Tech Lead

**Evidence File**: `app/vendor_catalog_app/backend/repository_mixins/common/core/audit.py`

---

### DRIFT-004: Input Validation Inconsistency

**Severity**: High

**Description**: Some forms validate input (length, format, type), others don't. Creates data quality issues and security risks.

**Prevention**:
- Define validation rules for all entity fields
- Use Pydantic models for form input validation
- Enforce max lengths, URL schemes, email formats
- See: [Security Checklist](../operations/security-checklist.md)

**Detection**:
- CI lint: Detect `form.get(...)` without adjacent validation (future enhancement)
- Manual: Review form handlers in `app/vendor_catalog_app/web/routers/**/*.py`

**Remediation**:
- Add Pydantic models for form inputs
- Standardize validation patterns across routers

**Owner**: Tech Lead

**Evidence File**: `app/vendor_catalog_app/web/utils/validation.py` (to be created)

---

### DRIFT-005: Foreign Key Orphans

**Severity**: High

**Description**: Records inserted with invalid foreign keys create orphaned data when parent entity doesn't exist.

**Prevention**:
- Validate FK existence before insert: `_ensure_vendor_exists(vendor_id)`
- Add helper methods in repository base class
- Consider database-level FK constraints (Databricks limitation noted)

**Detection**:
- Data quality check: Join child to parent and flag NULL parents
- Example: `SELECT * FROM core_vendor_contact c LEFT JOIN core_vendor v ON c.vendor_id = v.vendor_id WHERE v.vendor_id IS NULL`

**Remediation**:
- Delete orphaned records or reassign to valid parent
- Add FK validation to prevent recurrence

**Owner**: Data Lead

**Evidence File**: Repository write methods in `app/vendor_catalog_app/backend/repository_mixins/`

---

### DRIFT-006: Ingestion vs App Edit Conflicts

**Severity**: High

**Description**: Batch ingestion overwrites fields manually edited by users in the app. No clear survivorship strategy.

**Prevention**:
- Define ownership matrix: app-owned fields vs ingestion-owned fields
- Add `user_override_flag` to protect user edits
- Implement source priority: App > PeopleSoft > Zycus
- See: [Data Ownership & Survivorship](../architecture/data-ownership-and-survivorship.md)

**Detection**:
- Audit log review: User edits followed by batch load show overwrite pattern
- User complaints: "My changes disappeared"

**Remediation**:
- Implement field-level ownership and override flags
- Document ingestion mapping rules
- Add pre-merge validation in ingestion pipeline

**Owner**: Data Lead

**Evidence File**: `docs/architecture/data-ownership-and-survivorship.md`

---

### DRIFT-007: Raw SQL in Routers

**Severity**: Medium

**Description**: SQL strings embedded in router files violate repository pattern, make testing harder, spread SQL logic.

**Prevention**:
- All SQL must live in `app/vendor_catalog_app/sql/` external files or repository methods
- Router layer calls repository methods only
- No `f"SELECT"` or `.execute(` in `app/vendor_catalog_app/web/routers/`

**Detection**:
- CI lint: Grep routers for SQL keywords (SELECT, INSERT, UPDATE, DELETE)
- Lint rule: `ruff` custom rule to flag SQL in routers

**Remediation**:
- Extract SQL to repository method or SQL file
- Replace inline SQL with repository call

**Owner**: Tech Lead

**Evidence File**: `.ruff.toml` lint rules

---

### DRIFT-008: Template XSS via |safe Filter

**Severity**: Medium

**Description**: Jinja2 `| safe` filter in templates bypasses auto-escaping. If used on unsanitized user input, allows XSS.

**Prevention**:
- Sanitize all user content at write time using `bleach.clean()`
- Use `| safe` only on content sanitized before storage
- Document every `| safe` usage with comment explaining why safe

**Detection**:
- Manual review: Grep templates for `| safe`
- Code review: Check that content passed to `| safe` is sanitized

**Remediation**:
- Remove `| safe` or add sanitization at write time
- Verify no stored XSS payloads in database

**Owner**: Security Lead

**Evidence File**: `app/vendor_catalog_app/web/utils/markdown.py` (sanitization logic)

---

### DRIFT-009: Metric/Logging Inconsistency

**Severity**: Medium

**Description**: Some features emit metrics/logs, others don't. Creates observability blind spots.

**Prevention**:
- Standard logging pattern: Use structured logging with correlation IDs
- Standard metrics: Emit business + technical metrics for all major flows
- See: [Observability & Audit](../operations/observability-and-audit.md)

**Detection**:
- Review dashboards: Missing metrics for known features
- Log analysis: Gaps in request traces

**Remediation**:
- Add missing log statements following pattern in `infrastructure/logging.py`
- Add missing metrics following pattern in `infrastructure/observability.py`

**Owner**: Tech Lead

**Evidence File**: `app/vendor_catalog_app/infrastructure/observability.py`

---

### DRIFT-010: Test Coverage Decay

**Severity**: Medium

**Description**: New features added without tests. Coverage drops below threshold. Regressions go undetected.

**Prevention**:
- Require tests for all new features (Definition of Done)
- CI blocks PR if coverage drops below 80%
- Pattern: Unit tests for repository, integration tests for routers

**Detection**:
- CI coverage report: `pytest --cov --cov-fail-under=80`
- Coverage trend: Track over time in CI metrics

**Remediation**:
- Add missing tests to restore coverage
- Refactor untestable code to be testable

**Owner**: Tech Lead

**Evidence File**: `.github/workflows/ci.yml` coverage check

---

## Drift Detection Cadence

| Activity | Frequency | Owner | Action |
|----------|-----------|-------|--------|
| RBAC coverage test | Every PR | CI | Fail build if violations |
| Dependency vulnerability scan | Daily | CI | Alert security lead |
| Test coverage report | Every PR | CI | Fail if <80% |
| Schema version check | Every deploy | Deploy script | Fail if version mismatch |
| Audit completeness spot check | Weekly | Data Lead | Sample mutations, verify audit |
| Foreign key orphan check | Weekly | Data Lead | Run data quality SQL |
| Documentation review | Monthly | Tech Lead | Update stale docs |
| Drift SLO review | Monthly | Team retro | Review metrics, plan remediation |

## Drift Remediation Process

1. **Detect**: Automated check or manual review identifies drift
2. **Log**: Create issue with `drift` label, link to this threat model entry
3. **Triage**: Tech Lead assigns severity and owner
4. **Remediate**: Owner creates PR following [Definition of Done](definition-of-done.md)
5. **Prevent**: Add/update enforcement artifact (test, lint rule, CI check)
6. **Document**: Update threat model if new drift vector discovered

## Drift Escalation

- **Critical drift** (DRIFT-001, DRIFT-002, DRIFT-003): Fix within 1 sprint, block releases until fixed
- **High drift** (DRIFT-004, DRIFT-005, DRIFT-006): Fix within 2 sprints
- **Medium drift** (DRIFT-007, DRIFT-008, DRIFT-009, DRIFT-010): Fix within 1 quarter

## Adding New Drift Vectors

When new drift pattern discovered:

1. Add entry to this document following template
2. Create detection method (test, lint, CI check, manual process)
3. Update [Guardrails](guardrails.md) if rule is non-negotiable
4. Update [Definition of Done](definition-of-done.md) if checklist item needed
5. Communicate to team in standup/retro

---

Last updated: 2026-02-15
