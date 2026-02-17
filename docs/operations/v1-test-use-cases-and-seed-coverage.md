# V1 Functional Test Use Cases and Seed Coverage

This document defines the full functional test use-case inventory and the required test data coverage to validate each application workflow.

## Scope
- Environment: V1 schema + runtime compatibility layer
- Data policy: synthetic seed only (no POC migration)
- Goal: every major app function has representative test records and role contexts

## Seed Assets
- Local seed runner: `setup/v1_schema/run_v1_seed.py`
- Local baseline seed SQL: `setup/local_db/sql/seed/001_seed_reference_data.sql`
- Local help seed SQL: `setup/local_db/sql/seed/002_seed_help_center.sql`
- Local expanded dataset: `setup/local_db/seed_full_corporate.py` via `--seed-profile full`
- Databricks seed SQL: `setup/v1_schema/databricks/95_seed_reference_data.sql`, `setup/v1_schema/databricks/96_seed_help_center.sql`
- Databricks seed notebook: `setup/databricks/notebooks/v1_seed_data.ipynb`
- Coverage verifier: `setup/v1_schema/verify_test_seed_coverage.py`

## Use Cases by Functional Area

### 1) Platform Runtime and Health
1. App boot in local DB mode
2. Health endpoint check
3. Bootstrap diagnostics page load
4. Dashboard load with KPI/reporting dependencies

Required data:
- At least 1 active vendor, offering, invoice, contract, project
- Reporting views populated (`rpt_spend_fact`, `rpt_contract_renewals`, `rpt_contract_cancellations`)

### 2) Security, RBAC, and User Context
1. Admin user can perform write actions
2. Editor user can perform scoped writes
3. Viewer user is read-only
4. Role grant list and scope list render
5. Permission mappings are present for guarded endpoints
6. User directory search and lookup resolve principals

Required data:
- Active rows in `sec_role_definition`, `sec_role_permission`, `sec_user_role_map`, `sec_user_org_scope`
- Multiple users in `app_user_directory` + `app_employee_directory`
- User settings in `app_user_settings`

### 3) Vendor 360 Core Flows
1. Vendor list and detail load
2. Vendor ownership/contact/org assignment render
3. Vendor edit/change request lifecycle
4. Vendor identifier display and source lineage checks
5. Vendor document links and activity trail

Required data:
- Vendors with different lifecycle/risk tiers in `core_vendor`
- Related rows in `core_vendor_identifier`, `core_vendor_business_owner`, `core_vendor_contact`, `core_vendor_org_assignment`
- Change/audit rows in `audit_entity_change`
- Document links in `app_document_link`

### 4) Offering Flows
1. Offerings list by vendor
2. Offering profile update path
3. Offering contacts and owners
4. Offering tickets lifecycle
5. Offering invoice/budget variance reporting
6. Offering inbound/outbound data flow management

Required data:
- `core_vendor_offering`, `core_offering_business_owner`, `core_offering_contact`
- `app_offering_profile`, `app_offering_ticket`, `app_offering_invoice`, `app_offering_data_flow`

### 5) Contracts and Demos
1. Contract workspace list and contract detail
2. Contract renewal/cancellation reporting
3. Contract event timeline
4. Vendor demo outcomes and scoring details
5. Demo notes visibility

Required data:
- Contracts + events in `core_contract`, `core_contract_event`
- Demos + scores + notes in `core_vendor_demo`, `core_vendor_demo_score`, `core_vendor_demo_note`

### 6) Projects and Collaboration
1. Project list and detail pages
2. Project-vendor and project-offering mapping
3. Project demos and notes
4. Project document links and activity history
5. Owner reassignment and ownership coverage reporting

Required data:
- `app_project`, `app_project_vendor_map`, `app_project_offering_map`
- `app_project_demo`, `app_project_note`, `app_document_link`

### 7) Imports and Onboarding
1. Import source batches visible
2. Raw source payload tables queryable
3. Onboarding request/task/approval lifecycle
4. Vendor change request workflow

Required data:
- `src_ingest_batch`, `src_peoplesoft_vendor_raw`, `src_zycus_vendor_raw`, `src_spreadsheet_vendor_raw`
- `app_onboarding_request`, `app_onboarding_task`, `app_onboarding_approval`, `app_vendor_change_request`

### 8) Help Center
1. Help article list and detail rendering
2. Markdown sanitizer and link behavior
3. Feedback submission
4. Issue submission

Required data:
- `vendor_help_article`, `vendor_help_feedback`, `vendor_help_issue`

### 9) Audit, History, and Observability
1. Entity change events query
2. Workflow event query
3. Access event query
4. Usage log query
5. Historical snapshots available for vendor/offering/contract

Required data:
- `audit_entity_change`, `audit_workflow_event`, `audit_access_event`, `app_usage_log`
- `hist_vendor`, `hist_vendor_offering`, `hist_contract`

## Coverage Matrix Summary

| Domain | Baseline Seed | Full Seed | Databricks Seed |
|---|---:|---:|---:|
| Platform runtime/reporting smoke | ✅ | ✅ | ✅ |
| RBAC + user directory + scopes | ✅ | ✅ | ✅ |
| Vendor/Offering/Project CRUD test records | ✅ | ✅ | ✅ |
| Imports/onboarding workflow records | ✅ | ✅ | ✅ |
| Help center content + feedback/issue | ✅ | ✅ | ✅ |
| High-volume pagination/perf realism | ⚠️ limited | ✅ | ⚠️ limited |
| Broad ownership/reassignment scenarios | ⚠️ limited | ✅ | ⚠️ limited |

## Recommended Test Profiles

- CI smoke and endpoint gates: `baseline`
- UAT + exploratory + reporting validation: `full`
- Databricks environment functional sanity: notebook + baseline databricks seed

## Execution Commands

### Local (baseline)
```bash
python setup/v1_schema/run_v1_schema.py --target local --execute --recreate --db-path setup/local_db/twvendor_local_v1_test.db
python setup/v1_schema/run_v1_seed.py --target local --db-path setup/local_db/twvendor_local_v1_test.db --seed-profile baseline
python setup/v1_schema/verify_test_seed_coverage.py --db-path setup/local_db/twvendor_local_v1_test.db --profile baseline
```

### Local (full)
```bash
python setup/v1_schema/run_v1_seed.py --target local --db-path setup/local_db/twvendor_local_v1_test.db --seed-profile full
python setup/v1_schema/verify_test_seed_coverage.py --db-path setup/local_db/twvendor_local_v1_test.db --profile full
```

### Databricks
- Open `setup/databricks/notebooks/v1_seed_data.ipynb`
- Set widgets `catalog`, `schema`, and optionally `seed_sql_root`
- Run all cells

## Acceptance Rule
Seed is considered functionally complete only when:
1. `verify_test_seed_coverage.py` passes for the target profile.
2. Core test suites execute without missing-data failures in target environment.
3. Help/RBAC/reporting/project flows each have at least one active, linked scenario in data.
