USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

-- Idempotent baseline seed for V1 smoke + functional testing in Databricks.

DELETE FROM app_project_note;
DELETE FROM app_project_demo;
DELETE FROM app_project_offering_map;
DELETE FROM app_project_vendor_map;
DELETE FROM app_project;
DELETE FROM app_access_request;
DELETE FROM app_onboarding_approval;
DELETE FROM app_onboarding_task;
DELETE FROM app_onboarding_request;
DELETE FROM app_document_link;
DELETE FROM app_vendor_change_request;
DELETE FROM app_note;
DELETE FROM app_offering_data_flow;
DELETE FROM app_offering_ticket;
DELETE FROM app_offering_invoice;
DELETE FROM app_offering_profile;
DELETE FROM app_usage_log;
DELETE FROM app_user_settings;
DELETE FROM app_lookup_option;
DELETE FROM app_employee_directory;
DELETE FROM app_user_directory;
DELETE FROM hist_contract;
DELETE FROM hist_vendor_offering;
DELETE FROM hist_vendor;
DELETE FROM audit_entity_change;
DELETE FROM audit_workflow_event;
DELETE FROM audit_access_event;
DELETE FROM core_vendor_demo_note;
DELETE FROM core_vendor_demo_score;
DELETE FROM core_vendor_demo;
DELETE FROM core_contract_event;
DELETE FROM core_contract;
DELETE FROM core_offering_contact;
DELETE FROM core_offering_business_owner;
DELETE FROM core_vendor_offering;
DELETE FROM core_vendor_business_owner;
DELETE FROM core_vendor_org_assignment;
DELETE FROM core_vendor_contact;
DELETE FROM core_vendor_identifier;
DELETE FROM core_vendor;
DELETE FROM src_peoplesoft_vendor_raw;
DELETE FROM src_zycus_vendor_raw;
DELETE FROM src_spreadsheet_vendor_raw;
DELETE FROM src_ingest_batch;
DELETE FROM sec_user_org_scope;
DELETE FROM sec_user_role_map;
DELETE FROM sec_group_role_map;
DELETE FROM sec_role_permission;
DELETE FROM sec_role_definition;

INSERT INTO sec_role_definition
  (role_code, role_name, description, approval_level, can_edit, can_report, can_direct_apply, active_flag, updated_at, updated_by)
VALUES
  ('vendor_admin', 'Vendor Admin', 'Admin role', 3, true, true, true, true, current_timestamp(), 'seed:system'),
  ('vendor_editor', 'Vendor Editor', 'Editor role', 2, true, true, false, true, current_timestamp(), 'seed:system'),
  ('vendor_viewer', 'Vendor Viewer', 'Viewer role', 1, false, true, false, true, current_timestamp(), 'seed:system');

INSERT INTO sec_role_permission (role_code, object_name, action_code, active_flag, updated_at) VALUES
  ('vendor_admin', 'vendors', 'write', true, current_timestamp()),
  ('vendor_admin', 'projects', 'write', true, current_timestamp()),
  ('vendor_admin', 'admin', 'write', true, current_timestamp()),
  ('vendor_editor', 'vendors', 'write', true, current_timestamp()),
  ('vendor_editor', 'projects', 'write', true, current_timestamp()),
  ('vendor_viewer', 'vendors', 'read', true, current_timestamp()),
  ('vendor_viewer', 'projects', 'read', true, current_timestamp());

INSERT INTO app_user_directory
  (user_id, login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag, created_at, updated_at, last_seen_at)
VALUES
  ('usr-001', 'dev_admin', 'dev_admin@example.com', 'dev_admin', 'E1001', 'E1000', 'Dev', 'Admin', 'Dev Admin', true, current_timestamp(), current_timestamp(), current_timestamp()),
  ('usr-002', 'editor', 'editor@example.com', 'editor', 'E1002', 'E1001', 'Casey', 'Editor', 'Casey Editor', true, current_timestamp(), current_timestamp(), current_timestamp()),
  ('usr-003', 'viewer', 'viewer@example.com', 'viewer', 'E1003', 'E1001', 'Val', 'Viewer', 'Val Viewer', true, current_timestamp(), current_timestamp(), current_timestamp());

INSERT INTO app_employee_directory
  (login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag)
VALUES
  ('dev_admin', 'dev_admin@example.com', 'dev_admin', 'E1001', 'E1000', 'Dev', 'Admin', 'Dev Admin', 1),
  ('editor', 'editor@example.com', 'editor', 'E1002', 'E1001', 'Casey', 'Editor', 'Casey Editor', 1),
  ('viewer', 'viewer@example.com', 'viewer', 'E1003', 'E1001', 'Val', 'Viewer', 'Val Viewer', 1);

INSERT INTO sec_user_role_map (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at) VALUES
  ('dev_admin', 'vendor_admin', true, 'seed:system', current_timestamp(), null),
  ('editor', 'vendor_editor', true, 'seed:system', current_timestamp(), null),
  ('viewer', 'vendor_viewer', true, 'seed:system', current_timestamp(), null);

INSERT INTO sec_user_org_scope (user_principal, org_id, scope_level, active_flag, granted_at) VALUES
  ('dev_admin', 'IT-ENT', 'full', true, current_timestamp()),
  ('editor', 'IT-ENT', 'edit', true, current_timestamp()),
  ('viewer', 'IT-ENT', 'read', true, current_timestamp());

INSERT INTO src_ingest_batch (batch_id, source_system, source_object, extract_ts, loaded_ts, row_count, status) VALUES
  ('b-20260201-01', 'PeopleSoft', 'vendor', '2026-02-01 02:00:00', '2026-02-01 02:15:00', 2, 'loaded');

INSERT INTO core_vendor
  (vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, source_system, source_record_id, source_batch_id, source_extract_ts, updated_at, updated_by)
VALUES
  ('vnd-001', 'Microsoft Corporation', 'Microsoft', 'active', 'IT-ENT', 'medium', 'PeopleSoft', 'ps-v-1001', 'b-20260201-01', '2026-02-01 02:00:00', '2026-02-01 10:00:00', 'seed:system'),
  ('vnd-002', 'Salesforce, Inc.', 'Salesforce', 'active', 'SALES-OPS', 'low', 'PeopleSoft', 'ps-v-1002', 'b-20260201-01', '2026-02-01 02:00:00', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO core_vendor_identifier
  (vendor_identifier_id, vendor_id, identifier_type, identifier_value, is_primary, country_code, updated_at, updated_by)
VALUES
  ('vid-001', 'vnd-001', 'duns', '123456789', 1, 'US', '2026-02-01 10:00:00', 'seed:system'),
  ('vid-002', 'vnd-002', 'duns', '987654321', 1, 'US', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO core_vendor_contact
  (vendor_contact_id, vendor_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by)
VALUES
  ('con-001', 'vnd-001', 'account_manager', 'Alex Rivers', 'alex.rivers@example.com', '555-0101', 1, '2026-02-01 10:00:00', 'seed:system'),
  ('con-002', 'vnd-002', 'support', 'Jordan Lee', 'jordan.lee@example.com', '555-0142', 1, '2026-02-01 10:00:00', 'seed:system');

INSERT INTO core_vendor_offering
  (offering_id, vendor_id, offering_name, offering_type, lob, service_type, lifecycle_state, criticality_tier, updated_at, updated_by)
VALUES
  ('off-001', 'vnd-001', 'Microsoft 365', 'SaaS', 'Enterprise', 'Application', 'active', 'tier_1', '2026-02-01 10:00:00', 'seed:system'),
  ('off-002', 'vnd-001', 'Azure', 'Cloud', 'IT', 'Infrastructure', 'active', 'tier_1', '2026-02-01 10:00:00', 'seed:system'),
  ('off-003', 'vnd-002', 'Sales Cloud', 'SaaS', 'Sales', 'Application', 'active', 'tier_2', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO core_offering_business_owner
  (offering_owner_id, offering_id, owner_user_principal, owner_role, active_flag, updated_at, updated_by)
VALUES
  ('oown-001', 'off-001', 'dev_admin@example.com', 'platform_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
  ('oown-002', 'off-002', 'editor@example.com', 'technical_owner', 1, '2026-02-01 10:00:00', 'seed:system');

INSERT INTO core_offering_contact
  (offering_contact_id, offering_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by)
VALUES
  ('ocon-001', 'off-001', 'support', 'M365 Support Desk', 'm365-support@example.com', '555-2001', 1, '2026-02-01 10:00:00', 'seed:system'),
  ('ocon-002', 'off-002', 'escalation', 'Azure Escalation Lead', 'azure-escalation@example.com', '555-2002', 1, '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_offering_profile
  (offering_id, vendor_id, estimated_monthly_cost, implementation_notes, data_sent, data_received, integration_method,
   inbound_method, inbound_landing_zone, inbound_identifiers, inbound_reporting_layer, inbound_ingestion_notes,
   outbound_method, outbound_creation_process, outbound_delivery_process, outbound_responsible_owner, outbound_notes,
   updated_at, updated_by)
VALUES
  ('off-001', 'vnd-001', 62500.00, 'M365 enterprise tenant with SSO and DLP controls.', 'license_usage', 'identity_sync', 'api',
   'api', 'raw_zone', 'tenant_id', 'rpt_vendor_360', 'Daily API pull',
   'api', 'Automation pipeline', 'Governed delivery service', 'dev_admin@example.com', 'Baseline profile.',
   '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_offering_data_flow
  (data_flow_id, offering_id, vendor_id, direction, flow_name, method, data_description, endpoint_details, identifiers,
   reporting_layer, creation_process, delivery_process, owner_user_principal, notes, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('flow-001-in', 'off-001', 'vnd-001', 'inbound', 'M365 Inbound Usage Feed', 'api', 'License usage and tenant health.',
   'https://graph.microsoft.com/v1.0/reports', 'tenant_id, sku_id', 'rpt_vendor_360', null, null, 'dev_admin@example.com', 'Validated daily.',
   1, '2026-01-20 08:00:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_offering_ticket
  (ticket_id, offering_id, vendor_id, ticket_system, external_ticket_id, title, status, priority, opened_date, closed_date, notes,
   active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('tkt-001', 'off-001', 'vnd-001', 'ServiceNow', 'INC300001', 'M365 tenant DLP policy update', 'resolved', 'medium',
   '2026-01-08', '2026-01-11', 'Policy update completed.', 1, '2026-01-08 09:00:00', 'seed:system', '2026-01-11 16:30:00', 'seed:system');

INSERT INTO app_offering_invoice
  (invoice_id, offering_id, vendor_id, invoice_number, invoice_date, amount, currency_code, invoice_status, notes,
   active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('inv-001', 'off-001', 'vnd-001', 'MS365-2026-01', '2026-01-31', 62880.00, 'USD', 'paid', 'January billing cycle.',
   1, '2026-02-01 09:00:00', 'seed:system', '2026-02-03 09:00:00', 'seed:system');

INSERT INTO core_contract
  (contract_id, vendor_id, offering_id, contract_number, contract_status, start_date, end_date, cancelled_flag, annual_value, updated_at, updated_by)
VALUES
  ('ctr-101', 'vnd-001', 'off-002', 'MS-2024-001', 'active', '2024-04-01', '2026-03-15', 0, 1880000.0, '2026-02-01 10:00:00', 'seed:system'),
  ('ctr-202', 'vnd-002', 'off-003', 'SF-2024-210', 'active', '2024-06-01', '2026-04-01', 0, 745000.0, '2026-02-01 10:00:00', 'seed:system');

INSERT INTO core_contract_event
  (contract_event_id, contract_id, event_type, event_ts, reason_code, notes, actor_user_principal)
VALUES
  ('ce-001', 'ctr-101', 'renewal_planned', '2026-01-05 09:00:00', null, 'Preparing renewal proposal.', 'procurement@example.com'),
  ('ce-002', 'ctr-202', 'renewal_negotiation', '2026-01-12 11:30:00', null, 'Negotiation round 1.', 'sourcing@example.com');

INSERT INTO core_vendor_demo
  (demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes, updated_at, updated_by)
VALUES
  ('demo-001', 'vnd-001', 'off-002', '2026-01-10', 8.9, 'selected', null, 'Strong security and integration.', '2026-01-10 15:00:00', 'seed:system'),
  ('demo-002', 'vnd-002', 'off-003', '2026-01-11', 7.4, 'selected', null, 'Strong CRM workflow.', '2026-01-11 16:00:00', 'seed:system');

INSERT INTO core_vendor_demo_score
  (demo_score_id, demo_id, score_category, score_value, weight, comments)
VALUES
  ('ds-001', 'demo-001', 'security', 9.1, 0.3, 'Strong controls.'),
  ('ds-002', 'demo-001', 'integration', 8.8, 0.25, 'Good integration patterns.');

INSERT INTO core_vendor_demo_note
  (demo_note_id, demo_id, note_type, note_text, created_at, created_by)
VALUES
  ('dn-001', 'demo-001', 'selection_rationale', 'Selected due to security baseline.', '2026-01-10 15:00:00', 'architecture-board@example.com');

INSERT INTO app_vendor_change_request
  (change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at)
VALUES
  ('cr-001', 'vnd-001', 'dev_admin@example.com', 'update_contact', '{"contact":"new escalation"}', 'approved', '2026-01-15 10:00:00', '2026-01-16 09:00:00');

INSERT INTO app_project
  (project_id, vendor_id, project_name, project_type, status, start_date, target_date, owner_principal, description, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('prj-001', 'vnd-001', 'Defender Rollout FY26', 'implementation', 'active', '2026-01-05', '2026-06-30', 'dev_admin@example.com',
   'Expand Defender controls.', 1, '2026-01-05 09:00:00', 'seed:system', '2026-02-01 14:00:00', 'seed:system');

INSERT INTO app_project_vendor_map
  (project_vendor_map_id, project_id, vendor_id, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('pvm-001', 'prj-001', 'vnd-001', 1, '2026-01-05 09:00:00', 'seed:system', '2026-01-05 09:00:00', 'seed:system');

INSERT INTO app_project_offering_map
  (project_offering_map_id, project_id, vendor_id, offering_id, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('pom-001', 'prj-001', 'vnd-001', 'off-002', 1, '2026-01-05 09:00:00', 'seed:system', '2026-01-05 09:00:00', 'seed:system');

INSERT INTO app_project_demo
  (project_demo_id, project_id, vendor_id, demo_name, demo_datetime_start, demo_datetime_end, demo_type, outcome, score,
   attendees_internal, attendees_vendor, notes, followups, linked_offering_id, linked_vendor_demo_id, active_flag,
   created_at, created_by, updated_at, updated_by)
VALUES
  ('pdm-001', 'prj-001', 'vnd-001', 'Defender Deep Dive', '2026-01-28 13:00:00', '2026-01-28 14:30:00', 'workshop', 'follow_up', 7.4,
   'security team', 'defender specialists', 'Need additional endpoint coverage details.', 'Review roadmap.', 'off-002', 'demo-001', 1,
   '2026-01-28 15:00:00', 'seed:system', '2026-01-28 15:00:00', 'seed:system');

INSERT INTO app_project_note
  (project_note_id, project_id, vendor_id, note_text, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('pnt-001', 'prj-001', 'vnd-001', 'Initial kickoff complete.', 1, '2026-02-01 09:30:00', 'seed:system', '2026-02-01 09:30:00', 'seed:system');

INSERT INTO app_document_link
  (doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  ('doc-001', 'vendor', 'vnd-001', 'Vendor Master Packet', 'https://contoso.sharepoint.com/sites/vendor/Documents/Vendor_Master_Packet.pdf',
   'sharepoint', 'master,contract', 'dev_admin@example.com', 1, '2026-01-18 10:00:00', 'seed:system', '2026-01-18 10:00:00', 'seed:system');

INSERT INTO app_access_request
  (access_request_id, requester_user_principal, requested_role, justification, status, submitted_at, updated_at)
VALUES
  ('ar-001', 'viewer@example.com', 'vendor_editor', 'Need update access for sprint validation.', 'pending', '2026-02-02 09:00:00', '2026-02-02 09:00:00');

INSERT INTO app_onboarding_request
  (request_id, requestor_user_principal, vendor_name_raw, priority, status, submitted_at, updated_at)
VALUES
  ('onb-001', 'dev_admin@example.com', 'Contoso Managed Services', 'high', 'in_review', '2026-02-01 10:00:00', '2026-02-03 09:00:00');

INSERT INTO app_onboarding_task
  (task_id, request_id, task_type, assignee_group, due_at, status, updated_at, updated_by)
VALUES
  ('task-001', 'onb-001', 'risk_review', 'group:corp_security', '2026-02-08 17:00:00', 'open', '2026-02-03 09:00:00', 'seed:system');

INSERT INTO app_onboarding_approval
  (approval_id, request_id, stage_name, approver_user_principal, decision, decided_at, comments, updated_at)
VALUES
  ('apr-001', 'onb-001', 'security', 'dev_admin@example.com', 'approved', '2026-02-03 10:00:00', 'Security controls meet baseline.', '2026-02-03 10:00:00');

INSERT INTO app_lookup_option
  (option_id, lookup_type, option_code, option_label, sort_order, active_flag, valid_from_ts, valid_to_ts, is_current, deleted_flag, updated_at, updated_by)
VALUES
  ('lk-001', 'offering_type', 'saas', 'SaaS', 10, 1, '2025-01-01 00:00:00', null, 1, 0, '2026-02-01 10:00:00', 'seed:system'),
  ('lk-002', 'offering_type', 'cloud', 'Cloud', 20, 1, '2025-01-01 00:00:00', null, 1, 0, '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_user_settings
  (setting_id, user_principal, setting_key, setting_value_json, updated_at, updated_by)
VALUES
  ('set-001', 'dev_admin@example.com', 'dashboard_layout', '{"widgets":["kpis","renewals","spend"]}', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_usage_log (usage_event_id, user_principal, page_name, event_type, event_ts, payload_json) VALUES
  ('use-001', 'dev_admin@example.com', 'dashboard', 'page_view', '2026-02-03 08:00:00', '{"section":"kpis"}');

INSERT INTO audit_entity_change
  (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
VALUES
  ('ae-001', 'core_vendor', 'vnd-001', 'update', null, '{"display_name":"Microsoft"}', 'dev_admin@example.com', '2026-01-16 09:00:00', null);

INSERT INTO audit_workflow_event
  (workflow_event_id, workflow_type, workflow_id, old_status, new_status, actor_user_principal, event_ts, notes)
VALUES
  ('awf-001', 'onboarding', 'onb-001', 'submitted', 'in_review', 'dev_admin@example.com', '2026-02-03 09:00:00', 'Initial routing complete.');

INSERT INTO audit_access_event
  (access_event_id, actor_user_principal, action_type, target_user_principal, target_role, event_ts, notes)
VALUES
  ('aac-001', 'dev_admin@example.com', 'grant', 'editor@example.com', 'vendor_editor', '2026-02-03 09:00:00', 'Granted for testing.');

INSERT INTO hist_vendor
  (vendor_hist_id, vendor_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
VALUES
  ('hvend-001', 'vnd-001', 1, '2026-01-01 00:00:00', null, 1, '{"vendor_id":"vnd-001"}', 'seed:system', 'baseline');

INSERT INTO hist_vendor_offering
  (vendor_offering_hist_id, offering_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
VALUES
  ('hoff-001', 'off-001', 1, '2026-01-01 00:00:00', null, 1, '{"offering_id":"off-001"}', 'seed:system', 'baseline');

INSERT INTO hist_contract
  (contract_hist_id, contract_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
VALUES
  ('hctr-001', 'ctr-101', 1, '2026-01-01 00:00:00', null, 1, '{"contract_id":"ctr-101"}', 'seed:system', 'baseline');