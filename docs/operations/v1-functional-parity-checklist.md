# V1 Functional Parity Checklist

Use this checklist to ensure V1 cutover does not lose any current functionality.

Context:
- POC data migration is not required.
- Functional behavior parity is required.
- Improvements are allowed if backward outcomes are preserved.
- Deployment model is clean rebuild (drop and recreate target DB/schema).

Reference plan:
- `docs/architecture/14-v1-functional-parity-execution-plan.md`

---

## 1) Core Platform Runtime
- [ ] Deployment executed with destructive rebuild mode (`--recreate`) for target environment.
- [ ] V1 schema bootstrap succeeds in local mode.
- [ ] V1 schema bootstrap succeeds in Databricks mode.
- [ ] `/api/health` is green against V1 runtime.
- [ ] Bootstrap diagnostics page shows no missing runtime objects.

## 2) Security, Identity, and RBAC
- [ ] `app_user_directory` equivalent runtime behavior exists.
- [ ] `sec_user_role_map` runtime behavior exists.
- [ ] `sec_group_role_map` runtime behavior exists.
- [ ] `sec_user_org_scope` runtime behavior exists.
- [ ] `sec_role_definition` and `sec_role_permission` behavior exists.
- [ ] RBAC coverage tests pass in V1 mode.

## 3) Audit and Telemetry
- [ ] Entity change audit writes are preserved.
- [ ] Workflow audit writes are preserved.
- [ ] Access audit writes are preserved.
- [ ] Usage telemetry writes are preserved.

## 4) Vendor / Offering / Contract / Demo
- [ ] Vendor create/edit/detail works.
- [ ] Offering create/edit/detail works.
- [ ] Contract lifecycle workflows work.
- [ ] Demo lifecycle and scoring workflows work.
- [ ] Offering profile/ticket/invoice/dataflow workflows work.

## 5) Projects and Documents
- [ ] Project create/edit/detail works.
- [ ] Project vendor mapping works.
- [ ] Project offering mapping works.
- [ ] Project demo workflows work.
- [ ] Project notes workflows work.
- [ ] Document link workflows work across supported entity types.

## 6) Imports and Onboarding
- [ ] Source ingest batch tracking behavior exists.
- [ ] Source raw staging behavior exists for expected channels.
- [ ] Onboarding request/task/approval workflows work.
- [ ] Vendor change request workflow works.

## 7) Help and Reports
- [ ] Help article index/detail works.
- [ ] Help feedback and issue capture work.
- [ ] Reports run/preview/download/email request workflows work.

## 8) Mastering Enhancements (Improvement Track)
- [ ] `vendor_identifier` flows are active and tested.
- [ ] Merge event/member/snapshot/survivorship flows are active and tested.
- [ ] Canonical vendor resolution artifact exists and is used by reports.
- [ ] Stewardship queue for duplicate review exists.

---

## Runtime Object Inventory To Cover

Historically-used runtime objects that must be represented (native V1 or compatibility bridge) before cutover:

### Security / Access
- `sec_user_role_map`
- `sec_group_role_map`
- `sec_user_org_scope`
- `sec_role_definition`
- `sec_role_permission`

### Audit / Telemetry
- `audit_entity_change`
- `audit_workflow_event`
- `audit_access_event`
- `app_usage_log`

### Identity / User
- `app_user_directory`
- `app_user_settings`
- `app_access_request`
- `app_employee_directory`

### Workflow / Application
- `app_onboarding_request`
- `app_onboarding_task`
- `app_onboarding_approval`
- `app_vendor_change_request`
- `app_note`
- `app_lookup_option`
- `app_document_link`

### Projects
- `app_project`
- `app_project_vendor_map`
- `app_project_offering_map`
- `app_project_demo`
- `app_project_note`

### Vendor / Offering Domain
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
- `app_offering_profile`
- `app_offering_ticket`
- `app_offering_invoice`
- `app_offering_data_flow`

### History
- `hist_vendor`
- `hist_vendor_offering`
- `hist_contract`

### Source Ingestion
- `src_ingest_batch`
- `src_peoplesoft_vendor_raw`
- `src_spreadsheet_vendor_raw`
- `src_zycus_vendor_raw`

### Help
- `vendor_help_article`
- `vendor_help_feedback`
- `vendor_help_issue`

### Reporting Views
- `rpt_vendor_360`
- `rpt_vendor_demo_outcomes`
- `rpt_contract_cancellations`
- `rpt_contract_renewals`
- `rpt_spend_fact`
- `vw_employee_directory`
