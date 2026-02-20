# VendorCatalog Documentation Index

**Start Here**: This is the master index for all VendorCatalog documentation.

## Quick Actions

- **New developer onboarding**: Read [Governance Guardrails](governance/guardrails.md) then [Definition of Done](governance/definition-of-done.md)
- **Creating a PR**: Review [Pull Request Template](../.github/pull_request_template.md) and [Definition of Done](governance/definition-of-done.md)
- **Adding a feature**: Check [RBAC & Permissions](architecture/rbac-and-permissions.md) and [Guardrails](governance/guardrails.md)
- **Schema change**: Read [Migrations & Schema](operations/migrations-and-schema.md) first
- **Security review**: Use [Security Checklist](operations/security-checklist.md)
- **Production deployment**: Follow [Release Process](governance/release-process.md)
- **Investigating drift**: See [Drift Threat Model](governance/drift-threat-model.md)

## Documentation Structure

### Governance (Rules & Process)

The non-negotiable rules and processes that prevent drift.

- **[Drift Threat Model](governance/drift-threat-model.md)**: Top 10 drift vectors, prevention, detection, SLO targets
- **[Guardrails](governance/guardrails.md)**: Hard rules with enforcement (test/lint/CI)
- **[Definition of Done](governance/definition-of-done.md)**: Checklists for PRs (bug fix, feature, schema change)
- **[Release Process](governance/release-process.md)**: Branch strategy, PR requirements, rollback standards

### Architecture (Design Decisions)

How the system is designed and why.

- **[RBAC & Permissions](architecture/rbac-and-permissions.md)**: Roles, LOB-scoping, mutation patterns, common mistakes
- **[Data Ownership & Survivorship](architecture/data-ownership-and-survivorship.md)**: Entity ownership matrix, ingestion vs app edits, conflict resolution
- **[V1 Functional Parity Execution Plan](architecture/14-v1-functional-parity-execution-plan.md)**: No-data-migration plan to preserve all current functionality during V1 build-out
- **[Existing Architecture Docs](architecture/)**: Domain model, data model, security, ingestion, app architecture, NFRs

### Operations (Running the System)

How to build, test, deploy, and monitor the system.

- **[CI Quality Gates](operations/ci-quality-gates.md)**: Exact CI checks, how to run locally, failure triage
- **[Migrations & Schema](operations/migrations-and-schema.md)**: Migration workflow, version tracking, Databricks optimization
- **[Observability & Audit](operations/observability-and-audit.md)**: Logging, metrics, audit retention, alerting
- **[Security Checklist](operations/security-checklist.md)**: URL validation, XSS, secrets, rate limiting, dependency updates
- **[Imports Bundles Operations](operations/imports-bundles.md)**: Multi-file/ZIP imports wizard flow, dependency apply order, and reprocess behavior
- **[Current Application Capabilities, Gaps, and Enhancements](operations/current-application-capabilities-gaps-and-enhancements.md)**: Consolidated current-state and enhancement roadmap
- **[V1 Functional Parity Checklist](operations/v1-functional-parity-checklist.md)**: Cutover checklist to prevent functionality regressions

### Roadmap

- **[PR Bundles](roadmap/pr-bundles.md)**: Step-by-step execution plan to eliminate drift (5-8 PRs with acceptance criteria)

### Database

- **[Database README](database/README.md)**: Schema overview, table families, current state
- **[Schema Reference](database/schema-reference.md)**: Table-by-table documentation

### Configuration

- **[Environment Variables](configuration/environment-variables.md)**: Complete env var reference

### User Experience

- **[User Guide](user-guide.md)**: End-user documentation
- **[Click Budget](ux/click-budget.md)**: UX efficiency tracking
- **[Screen Audit](ux/screen-audit.md)**: Screen inventory and status
- **[Prioritized Backlog](ux/prioritized-backlog.md)**: UX improvements queue

### Changelog

- **[CHANGELOG.md](CHANGELOG.md)**: Timestamped feature history with change IDs

## Enforcement Artifacts

These files enforce the rules defined in governance docs:

- **[.github/workflows/ci.yml](../.github/workflows/ci.yml)**: Automated quality gates
- **[.github/pull_request_template.md](../.github/pull_request_template.md)**: PR checklist
- **[.github/CODEOWNERS](../.github/CODEOWNERS)**: Review responsibility
- **[tests/test_rbac_coverage.py](../tests/test_rbac_coverage.py)**: RBAC enforcement test
- **[app/vendor_catalog_app/web/security/rbac.py](../app/vendor_catalog_app/web/security/rbac.py)**: Permission decorator
- **[app/vendor_catalog_app/infrastructure/migrations.py](../app/vendor_catalog_app/infrastructure/migrations.py)**: Migration runner
- **[pyproject.toml](../pyproject.toml)**: Tool configuration (pytest, ruff, mypy)

## How to Use This Docs Pack

### For New Team Members

1. Read [Guardrails](governance/guardrails.md) (15 min)
2. Read [Definition of Done](governance/definition-of-done.md) (10 min)
3. Read [RBAC & Permissions](architecture/rbac-and-permissions.md) (20 min)
4. Scan [PR Bundles](roadmap/pr-bundles.md) to understand current priorities (10 min)

### For Code Reviews

1. Check PR against [Definition of Done](governance/definition-of-done.md)
2. If schema change: verify [Migrations & Schema](operations/migrations-and-schema.md) compliance
3. If mutation endpoint: verify [RBAC & Permissions](architecture/rbac-and-permissions.md) compliance
4. If security-sensitive: use [Security Checklist](operations/security-checklist.md)

### For Architecture Decisions

1. Document in `docs/architecture/decisions/` using [ADR template](architecture/templates/adr-template.md)
2. Update relevant governance/architecture docs
3. Update enforcement artifacts if new rule introduced

### For Drift Prevention

1. Review [Drift Threat Model](governance/drift-threat-model.md) monthly
2. Check SLO compliance (RBAC coverage, migration tracking, audit completeness)
3. Update threat model when new drift vectors discovered

## Documentation Standards

- **ASCII-safe**: All docs must be plain text friendly
- **Short sentences**: Prefer clarity over cleverness
- **Cross-link heavily**: Use relative paths
- **Evidence-based**: Link to code files, line numbers where applicable
- **Actionable**: Every rule has enforcement method

## Maintenance

- **Update frequency**: Update docs in same PR as code changes
- **Broken link check**: Run `grep -r '\[.*\](.*)' docs/` and verify paths quarterly
- **Drift review**: Review [Drift Threat Model](governance/drift-threat-model.md) monthly in team retro
- **Changelog**: Update [CHANGELOG.md](CHANGELOG.md) for every user-visible change

## Contact

- **Tech Lead**: [CODEOWNERS](../.github/CODEOWNERS)
- **Drift Questions**: Open issue with `drift` label
- **Doc Updates**: PR to `docs/` with updates

---

Last updated: 2026-02-15
