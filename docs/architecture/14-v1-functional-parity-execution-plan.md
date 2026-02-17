# 14. V1 Functional Parity Execution Plan (No POC Data Migration)

## Decision
POC data will not be migrated to V1. No legacy data conversion will be performed. This is a clean deployment.

This means V1 go-live criteria are based on **feature continuity and behavior quality**, not data carryover.

## Non-Negotiable Constraints
1. No current user-visible capability can be lost.
2. Existing workflows must remain available (or better) in V1.
3. Improvements are allowed only if they preserve existing outcomes.
4. Cutover can happen only after parity acceptance tests are green.
5. V1 deployment is destructive for target schema/database (`drop + recreate`).
6. No POC dataset conversion/backfill tasks are included in scope.

## Database Design Quality Gates (Scrutiny Readiness)
1. Every transactional table has a primary key.
2. Relationship tables declare foreign keys to parent entities.
3. Natural-key uniqueness is enforced where collisions would corrupt behavior.
4. Lifecycle state semantics are explicit (`active_flag`, revocation checks, temporal columns).
5. Quality verification is automated and must pass before cutover:
  - `python setup/v1_schema/verify_v1_schema_quality.py --db-path <local_v1_db>`

---

## Current Parity Reality
- Current app feature footprint was built against a broader runtime model (historically 50+ tables across `core_`, `app_`, `sec_`, `audit_`, `src_`, help).
- Current V1 schema package contains normalized foundation entities (25 tables) but does not yet cover all workflow/runtime objects required by the full application surface.

Result: switching runtime directly to V1 today would risk feature regression unless parity layers are completed.

## Deployment Model: Clean Rebuild
- Local deployment uses `--recreate` to delete the target SQLite DB before schema build.
- Databricks deployment uses `--recreate` to run `DROP SCHEMA ... CASCADE` then recreate baseline schema.
- Any prior data in target V1 schema is intentionally removed.
- Recommended operator path: `setup/v1_schema/deploy_v1_clean.ps1` (forces clean rebuild workflow).

---

## Functional Parity Scope (Must Be Preserved)

## A) Vendor and Offering
- Vendor create/edit/detail and ownership.
- Offering create/edit/detail and ownership/contacts.
- Contract and demo linkage from vendor/offering surfaces.
- Offering profile, invoice, ticket, and data-flow workflows.

## B) Projects
- Standalone project create/edit/detail.
- Multi-vendor and offering mappings.
- Project demos, notes, and document links.

## C) Imports and Onboarding
- Import ingestion support and staging entities.
- Onboarding request/task/approval and vendor change request flows.

## D) Security and Access
- User roles, group roles, scopes, role-permission mappings.
- Access request workflows.
- User directory and user settings continuity.

## E) Audit and Governance
- Entity change audit.
- Workflow audit.
- Access audit.
- Usage telemetry.

## F) Help and Reports
- Help article/feedback/issue flows.
- Existing report outputs and extract workflows.

---

## Implementation Strategy

## Track 1: Compatibility Bridge (Fastest Path to No-Regressions)
Create V1 compatibility objects so current app functionality runs while normalized V1 entities mature.

- Add compatibility table/view layer for runtime-required objects not yet represented.
- Keep naming compatibility for currently-used runtime surfaces.
- Mark compatibility artifacts as transitional and versioned.

## Track 2: Canonical V1 Domain Completion
Continue normalized V1 model expansion and merge-safe mastering improvements.

- Canonical vendor resolution object.
- Merge orchestration workflow.
- Stewardship queue and duplicate resolution lifecycle.

## Track 3: Progressive Router/Repository Refactor
Move app logic incrementally from compatibility objects to canonical V1 entities.

- Module-by-module refactor with parity tests required at each step.
- Remove compatibility artifacts only after all dependent code paths are migrated.

---

## Execution Waves

## Wave 1 (Immediate): Block Regressions
1. Add V1 compatibility DDL package for missing workflow/security/audit/help/reporting objects.
2. Add parity smoke tests for each major module:
   - vendor/offering,
   - projects,
   - imports/onboarding,
   - admin/RBAC,
   - reports/help.
3. Validate local runtime and bootstrap diagnostics against V1 schema package.

**Exit criteria**
- Existing core test suites remain green under V1 runtime mode.
- No module-level 404/500 regressions due to missing schema artifacts.

### Wave 1 Status (Current)
- `05_create_functional_parity_bridge.sql` implemented for security/audit/user/help runtime parity.
- `06_create_functional_runtime_compat.sql` implemented for source/core/history/app workflow parity objects.
- Local quality gate verification passes on clean build using `verify_v1_schema_quality.py`.
- Existing local DB files created before new constraints must be recreated or migrated to pick up added FKs/UNIQUE/CHECK constraints.

## Wave 2: Mastering Operations
1. Implement canonical resolution layer for downstream joins.
2. Implement merge orchestration service (event, members, snapshots, survivorship, repoint, finalize).
3. Add stewardship queue + SLA fields + reviewer actions.

**Exit criteria**
- Duplicate handling is no-loss and auditable.
- Canonical identity resolution is deterministic for all downstream consumers.

## Wave 3: Full Canonical Migration
1. Refactor repositories to canonical V1 entities as primary store.
2. Keep compatibility objects read-through/write-through only where still required.
3. Decommission compatibility objects after verification window.

**Exit criteria**
- Runtime no longer depends on transitional compatibility objects.
- All parity tests and quality gates pass.

---

## Test-First Acceptance Matrix

A release candidate is accepted only if all areas pass under V1 runtime:

- Vendor lifecycle CRUD + ownership
- Offering lifecycle CRUD + ownership/contacts
- Contract/demo management + mapping
- Project lifecycle + vendors/offerings/demos/docs/notes
- Admin roles/scopes/group-role management
- RBAC coverage test gate
- Help center article/detail/feedback/issue paths
- Reports run/preview/download/email request
- Bootstrap health and diagnostics

---

## Risks and Controls
- **Risk**: V1 schema cutover before parity bridge completion.
  - **Control**: hard gate on parity acceptance suite.
- **Risk**: Hidden dependency on legacy-named runtime objects.
  - **Control**: repository SQL inventory + runtime bootstrap validation.
- **Risk**: Regression from incremental refactors.
  - **Control**: module-level contract tests and RBAC coverage enforcement.

---

## Recommended Next Implementation Step
Implement **Wave 1 / Step 1** now:
- Create `05_create_functional_parity_tables.sql` in both local and Databricks V1 schema packages,
- add compatibility objects required by current workflows,
- then run targeted parity test slices module by module.

This is the most direct way to honor the requirement: **no data migration, no functionality loss.**
