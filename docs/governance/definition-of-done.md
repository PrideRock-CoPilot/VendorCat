# Definition of Done

This document defines completion criteria for different types of work. Use the appropriate checklist in PR descriptions.

## How to Use

1. Select the checklist matching your PR type
2. Copy checklist into PR description
3. Check each box as you complete it
4. Reviewer verifies all boxes checked before approval

## Bug Fix Definition of Done

Use for: Defect remediation, error handling improvements

- [ ] **Root cause identified**: Document why bug occurred in issue comment
- [ ] **Fix implemented**: Code change addresses root cause
- [ ] **Regression test added**: Test reproduces original bug, passes with fix
- [ ] **Manual test passed**: Verify fix in local dev environment
- [ ] **No new errors**: `pytest` passes, no new linting errors
- [ ] **Audit impact assessed**: If bug affected audit trail, document gap
- [ ] **Changelog updated**: Add entry to `docs/CHANGELOG.md` with bug ID

**Example PR Description**:
```
Fixes #456 - Vendor contact deletion fails with 500 error

Root cause: Missing FK validation caused orphaned contact records.

Checklist:
- [x] Root cause identified in #456
- [x] Fix implemented in repository.py
- [x] Regression test added: test_delete_nonexistent_contact()
- [x] Manual test passed
- [x] No new errors
- [x] Audit impact: none (deletion already audited)
- [x] Changelog updated
```

---

## Feature Definition of Done

Use for: New functionality, UI enhancements, API endpoints

- [ ] **Requirements documented**: Feature spec linked in PR (issue, ADR, or inline)
- [ ] **RBAC enforced**: All mutation endpoints have permission checks (Rule 1)
- [ ] **Input validated**: All user inputs validated (Rule 5)
- [ ] **Audit trail added**: Mutations log to audit_entity_change (Rule 3)
- [ ] **Tests written**: Unit + integration tests for happy path + error cases (Rule 8)
- [ ] **Test coverage >= 80%**: Run `pytest --cov`
- [ ] **UI tested manually**: Smoke test in local dev environment
- [ ] **Documentation updated**: User-facing docs in `docs/user-guide.md` if needed
- [ ] **Changelog updated**: Add entry to `docs/CHANGELOG.md`
- [ ] **Security review**: If handles sensitive data, reviewed per security checklist

**Example PR Description**:
```
Add vendor contact prioritization feature (#234)

Allows users to mark one contact as "preferred" for each vendor.

Checklist:
- [x] Requirements in #234
- [x] RBAC enforced: @require_permission("vendor_contact_edit")
- [x] Input validated: Pydantic model for is_preferred flag
- [x] Audit trail: _write_audit_entity_change on preference change
- [x] Tests written: test_vendor_contact_priority.py
- [x] Coverage: 84% (above threshold)
- [x] UI tested: Verified checkbox renders and persists
- [x] Docs updated: user-guide.md section 3.2
- [x] Changelog updated
- [x] Security review: N/A (no sensitive data)
```

---

## Schema Change Definition of Done

Use for: DDL changes, new tables, column additions/removals

- [ ] **Migration file created**: `setup/databricks/migration_NNN_description.sql` (Rule 2)
- [ ] **Migration number incremented**: Sequential from last migration
- [ ] **Version table updated**: Migration inserts into `app_schema_version`
- [ ] **Backward compatibility assessed**: Can old code run on new schema during rollout?
- [ ] **Rollback plan documented**: How to revert schema change (in migration comments)
- [ ] **Applied to dev environment**: Test migration on local SQLite first
- [ ] **Repository updated**: Code changes to use new schema (if applicable)
- [ ] **Tests updated**: Existing tests pass with new schema
- [ ] **Schema reference updated**: `docs/database/schema-reference.md` updated
- [ ] **Changelog updated**: Add entry to `docs/CHANGELOG.md`

**Example PR Description**:
```
Add is_preferred_contact column to core_vendor_contact (#345)

Supports vendor contact prioritization feature.

Checklist:
- [x] Migration file: migration_007_add_contact_preferred_flag.sql
- [x] Version incremented: 007
- [x] Version table updated: INSERT in migration
- [x] Backward compatible: Yes (new column has DEFAULT FALSE)
- [x] Rollback plan: ALTER TABLE DROP COLUMN (documented in migration)
- [x] Applied to dev: Local SQLite migration successful
- [x] Repository updated: get_vendor_contacts() now selects is_preferred
- [x] Tests updated: All 21 test files pass
- [x] Schema reference updated
- [x] Changelog updated
```

---

## Refactor Definition of Done

Use for: Code restructuring, performance improvements, tech debt reduction

- [ ] **Refactor goal documented**: Explain why refactoring (performance, readability, etc.)
- [ ] **Behavior preserved**: No functional changes to end users
- [ ] **Tests pass**: All existing tests pass without modification (proves behavior preserved)
- [ ] **Performance measured**: If perf refactor, document before/after metrics
- [ ] **No new violations**: Ruff, mypy, pytest pass
- [ ] **Manual smoke test**: Verify affected features work as before
- [ ] **Documentation updated**: If public API changed, update docs
- [ ] **Tech debt issue closed**: Link to tech debt issue being resolved

**Example PR Description**:
```
Extract vendor search SQL to external file (#567)

Refactor to comply with Rule 4 (no SQL in routers).

Checklist:
- [x] Goal: Move SQL from router to repository pattern
- [x] Behavior preserved: Search results identical
- [x] Tests pass: test_vendor_search.py passes unchanged
- [x] Performance: No change (same SQL, different location)
- [x] No new violations: Ruff passes
- [x] Smoke test: Vendor search page works identically
- [x] Docs: No user-facing changes
- [x] Closes tech debt issue #555
```

---

## Security Fix Definition of Done

Use for: Vulnerability remediation, dependency updates, security improvements

- [ ] **Vulnerability documented**: Link to CVE, Dependabot alert, or security issue
- [ ] **Severity assessed**: Critical/High/Medium/Low
- [ ] **Fix applied**: Code or dependency updated
- [ ] **Exploit test added**: Test that vulnerability is no longer exploitable
- [ ] **All tests pass**: No regressions introduced
- [ ] **Manual security test**: Attempt exploit in local environment (fails as expected)
- [ ] **Dependencies updated**: Run `pip list --outdated` and update related packages
- [ ] **Changelog updated**: Security fix noted in `docs/CHANGELOG.md`
- [ ] **Deployed within SLO**: Critical <7 days, High <14 days, Medium <30 days

**Example PR Description**:
```
Update Jinja2 to 3.1.4 (CVE-2024-XXXXX) (#789)

Fixes XSS vulnerability in template rendering.

Checklist:
- [x] Vulnerability: Dependabot alert #123, CVE-2024-XXXXX
- [x] Severity: High
- [x] Fix applied: requirements.txt updated to Jinja2==3.1.4
- [x] Exploit test: test_template_xss_blocked.py added
- [x] All tests pass
- [x] Manual security test: XSS payload blocked
- [x] Dependencies updated: pip list shows no outdated security-related packages
- [x] Changelog updated
- [x] Deployed: Alert received 2024-02-10, PR merged 2024-02-15 (within 7 day SLO)
```

---

## Definition of Done Enforcement

**In CI**:
- Test coverage check (must be >=80%)
- Linting passes (ruff, mypy)
- All tests pass
- RBAC coverage test passes

**In Code Review**:
- Reviewer verifies appropriate checklist used
- Reviewer checks all boxes ticked
- Reviewer spot-checks compliance (e.g., audit call present, migration file exists)

**Metrics**:
- Track % of PRs with checklist in description
- Track % of PRs passing all checklist items on first review
- Review quarterly and adjust checklists based on recurring issues

---

Last updated: 2026-02-15
