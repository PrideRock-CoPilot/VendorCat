# Vendor Catalog Architecture Pack

## Purpose
This folder contains the architecture baseline for building a Databricks-native Vendor Catalog application with governance, security, auditability, and business workflows in a single Unity Catalog schema.

## Target Outcome
- A production-ready Vendor Master capability across the enterprise.
- Controlled access by role, organization, and data sensitivity.
- Traceable onboarding, approval, and stewardship workflows.
- Analytics-ready vendor, risk, demo, and contract outcomes.
- Full retention of original source data and all user edits.

## How To Use This Pack
1. Run a design kickoff using `kickoff-checklist.md`.
2. Confirm scope and success metrics in `01-objectives-scope.md`.
3. Lock domain and table design in `03-domain-model.md` and `04-data-model-unity-catalog.md`.
4. Finalize controls in `05-security-governance.md`.
5. Finalize pipelines and operations in `06-ingestion-pipelines.md` and `09-environments-devops.md`.
6. Track unresolved decisions in `12-open-questions.md` and `decisions/`.

## Document Map
- `01-objectives-scope.md`: Business goals, scope, constraints, and KPIs.
- `02-business-capabilities.md`: End-to-end business capabilities and workflows.
- `03-domain-model.md`: Core entities, relationships, and lifecycle states.
- `04-data-model-unity-catalog.md`: Single-schema data model and Unity Catalog structure.
- `05-security-governance.md`: RBAC, masking, row filters, auditing, and compliance.
- `06-ingestion-pipelines.md`: Source integration patterns, quality, and orchestration.
- `07-application-architecture.md`: Databricks App architecture and module design.
- `08-non-functional-requirements.md`: SLOs, reliability, scalability, and testing.
- `09-environments-devops.md`: Environment model, CI/CD, and release controls.
- `10-implementation-roadmap.md`: Phased delivery plan and milestones.
- `11-risk-register.md`: Architecture risks with mitigation and owners.
- `12-open-questions.md`: Open decisions needed before build.

## Supporting Assets
- `kickoff-checklist.md`: Workshop and readiness checklist.
- `sql/`: Starter SQL for catalog and table bootstrap.
- `diagrams/`: System context and data flow diagrams.
- `templates/`: ADR, entity spec, workshop notes, source-to-target mapping, and role matrix templates.
- `decisions/`: Architecture decision records.

## Physical Model Constraint
- Use one schema only: `twvendor`.
- Recommended environment mapping: `vendor_dev.twvendor`, `vendor_stage.twvendor`, `vendor_prod.twvendor`.

## Table Naming Convention In `twvendor`
- `src_`: immutable source landing and source history tables.
- `core_`: current canonical business entities.
- `hist_`: full historical versions for canonical entities.
- `app_`: workflow and app write models.
- `sec_`: entitlements and policy mappings.
- `audit_`: immutable event and change logs.
- `rpt_`: serving views for app and analytics.

## Definition Of Done For Architecture
- Data model approved by Procurement, Finance, Risk, Security, and Data Platform owners.
- Access model approved by IAM/Security and Internal Audit.
- Pipeline design approved with source-system owners.
- NFR targets accepted and test strategy signed off.
- Delivery roadmap and team ownership agreed.
