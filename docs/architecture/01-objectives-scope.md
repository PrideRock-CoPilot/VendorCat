# Objectives And Scope

## Business Objectives
- Establish a single trusted vendor master across the organization.
- Reduce onboarding cycle time through standardized workflows.
- Improve compliance posture with auditable controls and approvals.
- Enable spend, risk, demo, and contract lifecycle analytics from governed data.
- Preserve original source records and all in-app edits without data loss.

## Success Metrics
- Vendor onboarding lead time reduced by at least 30 percent.
- Duplicate vendor creation rate below 1 percent.
- 100 percent of vendor updates linked to approval or change request records.
- 100 percent access to sensitive fields controlled by policy and audited.
- Data quality score above 98 percent for required fields in serving views.
- 100 percent of edits have before/after values and actor identity in audit logs.

## In Scope
- Vendor master data model and lifecycle management.
- Onboarding and change request workflows.
- Access control and security policy enforcement.
- Source ingestion from PeopleSoft, Zycus, and governed spreadsheet feeds.
- Stewardship workflows and operational dashboards.
- Demo scoring and rationale capture for non-selected vendors.
- Contract cancellation rationale and notes.
- Vendor ownership model including vendor applications, contacts, and internal business owners.

## Out Of Scope (Initial Release)
- Contract clause AI extraction and negotiation automation.
- Real-time external sanctions streaming.
- Full supplier performance management application suite.

## Assumptions
- Identity provider groups are available and maintained.
- Source systems can provide incremental loads or CDC exports.
- Databricks Unity Catalog is the enterprise governance layer.
- Databricks SSO is the only authentication path for the app.

## Constraints
- Must run in existing enterprise Databricks account model.
- Must satisfy internal audit and regulatory controls.
- Must use a single Unity Catalog schema named `twvendor`.
- Must avoid direct user access to raw sensitive fields where not required.
- Users without explicit entitlements are limited to view-only access in allowed app areas.

## Key Decisions Needed
- Canonical vendor ID generation strategy.
- Record survivorship logic for matching and merge.
- Final RPO/RTO targets by data domain.
- Approval flow for direct edits versus request-based edits.
