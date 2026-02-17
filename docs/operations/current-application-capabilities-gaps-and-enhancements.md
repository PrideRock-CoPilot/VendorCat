# Vendor Catalog Current-State Assessment

## Purpose
This document provides a single, practical view of:
1. what the current application can do today,
2. where it still falls short,
3. what enhancements should be prioritized next.

It is intended to guide product, architecture, and delivery planning as the platform moves from POC patterns to a durable V1 operating model.

---

## 1) What The Current Application Can Do

### 1.1 Platform and Runtime
- Runs as a FastAPI + server-rendered Jinja application.
- Supports two runtime modes:
  - Local SQLite mode for development and test.
  - Databricks SQL / Unity Catalog mode for production-style deployment.
- Supports Databricks auth via PAT or OAuth service principal.
- Supports environment-based schema targeting (`TVENDOR_FQ_SCHEMA` or catalog+schema).
- Provides health endpoint (`/api/health`) and bootstrap diagnostics behavior.

### 1.2 Identity, Access, and Security
- Uses role-based access control (RBAC) patterns with mutation endpoint enforcement.
- Includes role/scope grant management in admin surfaces.
- Supports user directory persistence (`app_user_directory`) so audit trails retain user identity continuity.
- Supports production SQL safety policy controls (write-verb allowlist and DDL guardrails in production mode).

### 1.3 Core Business Workflows
- Vendor 360 management:
  - Create vendors.
  - Edit vendor profiles and ownership context.
  - Manage vendor-linked offerings.
- Offering management:
  - Create offerings under vendors.
  - Manage offering-level ownership and contacts.
  - Manage offering profile and mapped records (contracts/demos).
- Projects workspace:
  - Create standalone projects.
  - Link vendors and offerings.
  - Manage project-level notes, docs, demos, ownership.
  - Support multi-vendor project mapping behavior.
- Contracts and demos:
  - Track contract lifecycle and cancellation reasons.
  - Track demos and outcomes.
- Imports:
  - Supports import-related routing and validation paths with improved preview UX.

### 1.4 Reporting and Extracts
- Reports workspace with permission-aware access.
- Supports filtered report runs and preview.
- Supports CSV download endpoint.
- Supports queued email extract request capture.
- Tracks telemetry for run/download/email-request report actions.

### 1.5 Auditability and Governance Support
- Tracks app-level usage and event patterns for key write/report actions.
- Supports change request and workflow event patterns in current architecture.
- Includes architecture/governance/runbook documentation set:
  - guardrails,
  - definition of done,
  - release process,
  - migration and schema guidance,
  - production readiness checklist.

### 1.6 UX Maturity Achieved So Far
- Completed high-friction UX backlog items (typeahead, revokes, visibility, approvals triage, etc.).
- Reduced raw-ID workflows in key areas.
- Added pagination/sort/search improvements in Vendor 360.
- Improved ownership UX behavior and consistency across vendor/offering flows.

---

## 2) Data-Layer Progress Toward V1

### 2.1 V1 Foundation Delivered
- Legacy schema-creation assets have been archived.
- New V1 schema package exists for:
  - Local DB execution (`setup/v1_schema/local_db/*`),
  - Databricks execution (`setup/v1_schema/databricks/*`).
- V1 Databricks schema notebook exists with parameterization (`catalog`, `schema`, `environment`) and one-table-per-cell setup.
- V1 architecture document and ERD are in place (`docs/architecture/13-v1-data-layer-rebuild.md`).
- Orchestration helper exists for ordered schema execution (`setup/v1_schema/run_v1_schema.py`).

### 2.2 Advanced Mastering Structures Added
- `vendor_identifier` table added for deterministic cross-system vendor key mapping.
- Merge lineage and survivorship model introduced:
  - `vendor_merge_event`,
  - `vendor_merge_member`,
  - `vendor_merge_snapshot`,
  - `vendor_survivorship_decision`.
- This enables no-loss merge history and audit-ready merge traceability.

---

## 3) Current Shortcomings / Gaps

### 3.1 Biggest Gap: Operating Model vs. Data Model
The schema now includes key mastering entities, but the application does not yet fully operationalize them end-to-end.

Still missing or partial:
- Canonical entity resolution mechanism for downstream consumers (for example, a canonical survivor mapping view).
- Full merge execution workflow service (validate, snapshot, survivorship decisions, repoint, finalize).
- Stewardship queue for potential duplicates and unresolved match candidates.
- Confidence/explanation model and reviewer decision workflow for auto-match suggestions.

### 3.2 Ingestion/Reconciliation Lifecycle Is Not Fully Productized
- Backfill/reconciliation workflow from legacy free-form values to governed lookup keys is documented at high level but not fully operationalized as a productized pipeline.
- Unmapped-value handling and triage loops need explicit runtime workflows and ownership.

### 3.3 Governance Depth Still Evolving
- Governance structures exist, but compliance-style controls remain maturity targets:
  - stricter release gating tied to migration readiness,
  - stronger policy-as-code for schema and permission drift,
  - fuller operational runbooks for data stewardship incidents.

### 3.4 Production Hardening Opportunities
- End-to-end performance characterization under production-like scale should be formalized (especially search/typeahead/report workloads).
- Disaster recovery and rollback drills for schema and merge operations should be routinely executed and documented.

### 3.5 Functional Expansion Candidates
- Help and reporting are present, but enterprise-operating depth can be expanded:
  - richer SLA/exception handling around requests/queues,
  - tighter observability correlation across user action -> workflow -> data state transitions,
  - deeper data quality dashboards (unknown values, duplicate candidates, merge aging).

---

## 4) Enhancement Roadmap (Prioritized)

## Priority 0 (Must Have Next)
1. **Canonical Vendor Resolution Layer**
   - Add canonical resolution artifact (view/table) that maps every known vendor record and external key to current survivor vendor.
   - Make all downstream reports and joins consume this canonical layer.

2. **Merge Execution Workflow (No-Loss, Audited)**
   - Implement application/service workflow to:
     - create merge event,
     - record participants,
     - capture immutable snapshots,
     - store survivorship decisions,
     - repoint dependent rows safely,
     - mark merge status and completion metadata.

3. **Stewardship Queue for Match/Merge Review**
   - Add queue + status model for candidate duplicates.
   - Add assignment/escalation/SLA fields.
   - Add explicit approve/reject/reopen actions with audit events.

## Priority 1 (High Value)
4. **Deterministic Matching Framework**
   - Add match rules, confidence scoring, and explanation payloads.
   - Support both exact-key and fuzzy-name/address strategies.
   - Persist rationale for human review and model tuning.

5. **Data Reconciliation Productization**
   - Build repeatable reconciliation pipeline for unmapped governed values.
   - Add managed `UNMAPPED_*` triage dashboard and closure workflow.

6. **Canonical Read APIs and Contract Stabilization**
   - Expose stable read endpoints for canonical vendor identity and lineage retrieval.
   - Version response contracts for downstream consumers.

## Priority 2 (Scale and Resilience)
7. **Performance and Capacity Baselines**
   - Define p95 SLAs for major workflows (search, report, merge execution).
   - Add synthetic load tests and baseline dashboards.

8. **Operational Resilience and Recovery Playbooks**
   - Add merge rollback strategy for failed in-flight operations.
   - Add runbooks for reconciliation backlog spikes and duplicate storms.

9. **Quality and Drift Gates Expansion**
   - Extend CI gates to include schema integrity checks, migration safety checks, and higher RBAC/assertion coverage.

---

## 5) Recommended Enhancement Bundle “Like The Above”

If the goal is to continue in the same direction as recent work (identifier + merge lineage), the next single implementation bundle should be:

1. Add `vw_vendor_canonical_resolution` (or equivalent canonical table).
2. Implement merge orchestration service + repository methods.
3. Add stewardship queue tables/routes/UI entry points.
4. Add tests for canonical join behavior and merge no-loss guarantees.
5. Add runbook: “safe merge execution + rollback/compensation strategy.”

This bundle is the highest-leverage step to convert the new V1 schema from “well-modeled” to “operationally complete.”

---

## 6) Definition of “V1 Operationally Complete”

The application should be considered operationally complete for V1 when all are true:
- Governed dimensions are key-based only (no free-form drift writes).
- Canonical vendor resolution is the default join path for downstream use.
- Merge operations are no-loss, reproducible, and fully auditable.
- Stewardship queue controls unresolved match ambiguity.
- Reconciliation and unmapped-value handling are continuous, not ad hoc.
- Production gates enforce migration, RBAC, and quality controls reliably.

---

## 7) Current State Summary

The platform already provides substantial business functionality (vendor/offering/project/report/admin workflows) and has made strong progress on UX, RBAC, and schema modernization. The largest remaining gap is not table design—it is the mastering operating model that turns `vendor_identifier` and merge lineage into a reliable day-2 process for canonical identity at scale.
