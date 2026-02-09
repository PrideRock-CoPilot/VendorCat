# Schema Reference (`twvendor`)

The Vendor Catalog logical model currently includes 40 tables and 3 reporting views.

## `src_` Source Landing
- `src_ingest_batch`
- `src_peoplesoft_vendor_raw`
- `src_zycus_vendor_raw`
- `src_spreadsheet_vendor_raw`

## `core_` Canonical Entities
- `core_vendor`
- `core_vendor_identifier`
- `core_vendor_contact`
- `core_vendor_org_assignment`
- `core_vendor_business_owner`
- `core_vendor_offering`
- `core_offering_business_owner`
- `core_offering_contact`
- `core_contract`
- `core_contract_event`
- `core_vendor_demo`
- `core_vendor_demo_score`
- `core_vendor_demo_note`

## `hist_` Historical Versions
- `hist_vendor`
- `hist_vendor_offering`
- `hist_contract`

## `audit_` Immutable Audit
- `audit_entity_change`
- `audit_workflow_event`
- `audit_access_event`

## `app_` Application Workflow
- `app_onboarding_request`
- `app_vendor_change_request`
- `app_onboarding_task`
- `app_onboarding_approval`
- `app_access_request`
- `app_note`
- `app_user_settings`
- `app_usage_log`
- `app_project`
- `app_project_vendor_map`
- `app_project_offering_map`
- `app_project_demo`
- `app_project_note`
- `app_document_link`

## `sec_` Security And Entitlements
- `sec_user_role_map`
- `sec_user_org_scope`
- `sec_role_permission`

## `rpt_` Reporting Views
- `rpt_vendor_360`
- `rpt_vendor_demo_outcomes`
- `rpt_contract_cancellations`

## High-Value Relationships
- Vendor to offering: `core_vendor.vendor_id -> core_vendor_offering.vendor_id`
- Vendor to contract: `core_vendor.vendor_id -> core_contract.vendor_id`
- Vendor to demo: `core_vendor.vendor_id -> core_vendor_demo.vendor_id`
- Project to vendor (many-to-many): `app_project_vendor_map`
- Project to offering (many-to-many): `app_project_offering_map`
- Project to documents: `app_document_link` (`entity_type='project'`)
- Offering/vendor/demo documents: `app_document_link` via `entity_type`

## Mutable Tables Standard Columns
Mutable business/workflow tables should maintain:
- `created_at`
- `created_by`
- `updated_at`
- `updated_by`

## Audit Rule
All direct-apply writes should append an `audit_entity_change` record and emit usage telemetry.
