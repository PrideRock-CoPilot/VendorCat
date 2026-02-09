# Domain Model

## Bounded Contexts
- Vendor Master: canonical identity and core attributes.
- Compliance: certifications, tax, sanctions, and due diligence status.
- Relationship: parent-subsidiary, ownership, and internal org assignments.
- Portfolio: vendor offerings and application inventory.
- Workflow: onboarding, approvals, and change management.
- Access: entitlement mappings and audit trails.
- Source Lineage: immutable imported records from external systems.

## Canonical Entities
- `Vendor`
- `VendorIdentifier`
- `VendorSite`
- `VendorContact`
- `VendorBusinessOwner`
- `VendorOffering`
- `OfferingBusinessOwner`
- `OfferingContact`
- `VendorTaxProfile`
- `VendorBankAccount`
- `VendorCompliance`
- `VendorDocument`
- `VendorRelationship`
- `VendorOrgAssignment`
- `VendorStatusHistory`
- `VendorRiskAssessment`
- `Contract`
- `ContractLifecycleEvent`
- `VendorDemo`
- `VendorDemoScore`
- `VendorDemoOutcomeNote`
- `OnboardingRequest`
- `OnboardingTask`
- `OnboardingApproval`
- `VendorChangeRequest`
- `AccessRequest`
- `SourceRecord`
- `EntityHistory`
- `AuditEvent`

## Relationship Rules
- One vendor can have many identifiers, sites, contacts, documents, and risk assessments.
- One vendor can have many offerings/applications.
- One offering can have many internal business owners and external contacts.
- One vendor can map to many internal organizations through assignment rules.
- One onboarding request can have many tasks and approvals.
- One vendor can have many change requests over time.
- One contract can have many lifecycle events including cancellation.
- One vendor can have many demos, each with many scores and notes.
- Every canonical entity change must emit an audit event.

## Lifecycle States
- `draft`
- `submitted`
- `in_review`
- `approved`
- `active`
- `suspended`
- `retired`

## Identity Strategy
- Primary key for vendor: `vendor_id` (surrogate UUID).
- Business keys kept in `vendor_identifier` with type codes.
- Source records tracked with `source_system`, `source_record_id`, `source_extract_ts`, and immutable payload.
- Current-state tables are paired with full history tables keyed by version.

## Data Stewardship Rules
- Every active vendor must have required legal name, primary country, and owner org.
- Sensitive fields must have classification tags and controlled access paths.
- Deactivated vendors remain queryable for audit with lifecycle end date.
- Manual user edits never overwrite original source rows; they append new entity versions.
- Contract cancellation requires reason code and free-text notes.
- Demo non-selection requires reason code and supporting notes.
