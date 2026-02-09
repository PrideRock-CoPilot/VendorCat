# Data Model And Unity Catalog Design

## Physical Layout Constraint
- Single schema only: `twvendor`.
- Recommended environment mapping: `vendor_dev.twvendor`, `vendor_stage.twvendor`, `vendor_prod.twvendor`.

## Table Families Inside `twvendor`
- `src_`: immutable source ingest tables and source snapshots.
- `core_`: canonical current-state entities used by the app.
- `hist_`: full version history for canonical entities.
- `app_`: onboarding, approvals, and request workflows.
- `sec_`: entitlement and permission mapping.
- `audit_`: immutable event trail and change details.
- `rpt_`: secure views for app and analytics.

## External Source Coverage
- `src_zycus_vendor_raw`: raw ingest from Zycus.
- `src_peoplesoft_vendor_raw`: raw ingest from PeopleSoft.
- `src_spreadsheet_vendor_raw`: raw ingest from approved spreadsheets.
- `src_ingest_batch`: ingest batch metadata and source lineage.

## Core Vendor Inventory
- `core_vendor`: canonical vendor profile and lifecycle.
- `core_vendor_identifier`: business identifiers (DUNS, TIN, VAT, ERP IDs).
- `core_vendor_contact`: external vendor contacts.
- `core_vendor_business_owner`: internal business owners for vendor relationship.
- `core_vendor_offering`: offerings/applications provided by a vendor.
- `core_offering_business_owner`: internal business owners per offering.
- `core_offering_contact`: offering-level support/sales contacts.
- `core_vendor_org_assignment`: internal org access and assignment.
- `core_contract`: contract header and status.
- `core_contract_event`: contract lifecycle events including cancellation.
- `core_vendor_demo`: demo events and metadata.
- `core_vendor_demo_score`: weighted scoring breakdown by category.
- `core_vendor_demo_note`: notes including non-selection rationale.

## History And Audit Inventory
- `hist_vendor`: SCD2-style history for vendor profile versions.
- `hist_vendor_offering`: history for offering/application versions.
- `hist_contract`: history for contract versions.
- `audit_entity_change`: before/after row snapshots and actor metadata.
- `audit_workflow_event`: workflow state transition event log.
- `audit_access_event`: privileged access actions and permission changes.

## Workflow And Permission Inventory
- `app_onboarding_request`
- `app_onboarding_task`
- `app_onboarding_approval`
- `app_vendor_change_request`
- `app_access_request`
- `app_note`
- `sec_user_role_map`
- `sec_user_org_scope`
- `sec_role_permission`

## Modeling Standards
- Use Delta for all persisted tables.
- Use append-only inserts for `src_` and `audit_` tables.
- Use current plus history pattern for editable `core_` entities.
- Include `created_at`, `created_by`, `updated_at`, `updated_by` on mutable business tables.
- Include `version_no`, `valid_from_ts`, `valid_to_ts`, `is_current` on `hist_` tables.
- Track source lineage fields on core rows: `source_system`, `source_record_id`, `source_batch_id`, `source_extract_ts`.

## Edit And Audit Behavior
- User edits write through controlled app workflows.
- Approved edits update `core_` tables and append to `hist_` and `audit_` tables.
- Original source rows in `src_` tables are never overwritten or deleted.

## Data Contract Requirements
- Define source owner, technical owner, and SLA for each source feed.
- Define reconciliation checks for each ingest batch.
- Define mandatory columns and value domains for each `core_` entity.
