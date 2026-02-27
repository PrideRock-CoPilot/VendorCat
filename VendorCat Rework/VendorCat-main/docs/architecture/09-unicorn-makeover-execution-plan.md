# Unicorn Makeover Execution Plan

## 1) Mission
Build the VMO platform that becomes the system of record for vendor decisions, replacing spreadsheet-driven workflows with governed, auditable, and fast Databricks-native operations.

## 2) Product Pillars
1. Trusted Data: one canonical vendor/offering/project/contract view with provenance.
2. Decision Velocity: users can find, compare, evaluate, and approve faster than current manual process.
3. Governance by Default: every critical action is permissioned, auditable, and policy-backed.
4. Operational Excellence: predictable latency, clear loading states, and no ambiguous workflow states.

## 3) Non-Negotiables
1. SQL in files only.
2. No mock data paths in production code.
3. Role-driven access and explicit approval workflow.
4. Full audit events for create/update/delete/approve/deny.
5. Every page has clear empty states, pagination standards, and filter reset behavior.

## 4) North-Star KPIs
1. Time-to-onboard vendor: target < 2 business days.
2. Time-to-answer vendor question: target < 2 minutes.
3. % vendor records with required governance attributes: target > 98%.
4. % workflows completed in-app (not off-platform): target > 95%.
5. Median page transition latency: target < 2.5s (P95 < 5s).

## 5) Delivery Waves

### Wave A: Platform Reliability + UX Consistency
Scope:
1. Standard data-grid component behavior across tabs (paging, sorting, filters, empty states).
2. Unified loading UX (already in progress) with route and action-level transitions.
3. Query observability dashboard: slow SQL list, route timing, cache hit rate.
4. Caching policy by dataset type (reference, session, transactional).

Exit Criteria:
1. No page without pagination policy.
2. No route without latency logging.
3. P95 route latency reduced by at least 40% in local and Databricks dev.

### Wave B: Vendor Master + Identity Resolution
Scope:
1. Canonical vendor identity rules and duplicate review queue.
2. Override/provenance layer for source-vs-curated-vs-user-entered data.
3. Stewardship inbox for missing required attributes and stale records.

Exit Criteria:
1. Duplicate candidates surfaced with merge/ignore actions.
2. Field-level provenance visible in Vendor 360.

### Wave C: Decision Workbench (Projects, Demos, Contracts)
Scope:
1. Demo lifecycle orchestration with stage gates and weighted review forms (delivered in first iteration).
2. Contract intelligence: renewal risk, cancellation reasons, negotiation timeline.
3. Project-centric decision timelines linking all vendor actions.

Exit Criteria:
1. Full decision timeline per project with documents, outcomes, and approvals.
2. Contract dashboard supports proactive renewals and risk scoring.

### Wave D: Governance + Enterprise Integrations
Scope:
1. ERP/CRM ingestion normalization with conflict detection.
2. Role and scope governance hardening (single active role semantics).
3. Audit and compliance reporting packs (SOX/GDPR evidence views).

Exit Criteria:
1. End-to-end traceability from source feed to user decision.
2. Production-ready governance review signoff.

## 6) Immediate Sprint Backlog (Start Here)
1. UX Consistency Framework
   - Extract reusable table/pagination/filter partials.
   - Normalize page-size options and query param behavior.
2. Dark Mode Implementation
   - Add CSS variables for dark theme.
   - Implement theme toggle button in header.
   - Add JavaScript for theme switching and localStorage persistence.
3. Demo Workspace Completion
   - Add reviewer assignment and role-based scoring visibility.
   - Add review export and score normalization audit.
4. Performance Hardening
   - Add route-level query budget thresholds.
   - Add cache invalidation map by write action.
5. Data Stewardship Seed
   - Add required-field ruleset for vendor/offering/contract entities.
   - Add simple “Data Quality” admin panel.

## 7) Technical Design Standards
1. Module boundaries
   - `web/routers/<domain>/` routes only, no query logic.
   - `backend/repository_mixins/domains/<domain>/` for data operations.
   - `sql/` as single source of query truth.
2. View model shaping in router `common.py` helpers.
3. No direct DB calls in templates or frontend scripts.
4. New features must include:
   - SQL files,
   - route test coverage,
   - negative-path test coverage,
   - basic performance logging.

## 8) Risks and Mitigations
1. Risk: feature growth outpaces consistency.
   - Mitigation: enforce reusable page and table conventions before new domains.
2. Risk: Databricks SQL latency spikes.
   - Mitigation: caching tiers, async/background writes, and route query budgets.
3. Risk: governance complexity blocks adoption.
   - Mitigation: progressive policy rollout and guided request-access UX.

## 9) Definition of "Unicorn"
The app is a unicorn when a VMO user can:
1. find the right vendor/offering in under 60 seconds,
2. complete a compliant decision workflow without leaving the app,
3. explain any decision with full data and audit evidence in under 5 minutes.
