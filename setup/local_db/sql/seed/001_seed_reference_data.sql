PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Reset seeded entities so running seed multiple times stays deterministic.
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
DELETE FROM app_user_directory;
DELETE FROM app_employee_directory;
DELETE FROM hist_contract;
DELETE FROM hist_vendor_offering;
DELETE FROM hist_vendor;
DELETE FROM audit_entity_change;
DELETE FROM audit_workflow_event;
DELETE FROM audit_access_event;
DELETE FROM change_event;
DELETE FROM change_request;
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

-- Seed role definitions early because downstream tables enforce FK references.
INSERT INTO sec_role_definition (role_code, role_name, description, approval_level, can_edit, can_report, can_direct_apply, active_flag, updated_at, updated_by) VALUES
('vendor_admin', 'Vendor Admin', 'Full administrative access across all workflows and data changes.', 3, 1, 1, 1, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_steward', 'Vendor Steward', 'Data steward with elevated review/apply rights for governed updates.', 2, 1, 1, 1, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_editor', 'Vendor Editor', 'Contributor role for day-to-day edits and change submissions.', 1, 1, 1, 0, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_viewer', 'Vendor Viewer', 'Read-only access to vendor inventory and metadata.', 0, 0, 0, 0, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_auditor', 'Vendor Auditor', 'Read/report access for governance and audit functions.', 0, 0, 1, 0, 1, '2026-01-01 00:00:00', 'bootstrap');

-- Seed user principals early because app_user_settings enforces FK to app_user_directory(login_identifier).
INSERT INTO app_user_directory (user_id, login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag, created_at, updated_at, last_seen_at) VALUES
('usr-001', 'admin@example.com', 'admin@example.com', 'admin', 'E1001', 'E1000', 'Admin', 'User', 'Admin User', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-002', 'bob.smith@example.com', 'bob.smith@example.com', 'bsmith', 'E1002', 'E1001', 'Bob', 'Smith', 'Bob Smith', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-003', 'amy.johnson@example.com', 'amy.johnson@example.com', 'ajohnson', 'E1003', 'E1001', 'Amy', 'Johnson', 'Amy Johnson', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00');

INSERT INTO src_ingest_batch (batch_id, source_system, source_object, extract_ts, loaded_ts, row_count, status) VALUES
('b-20260201-01', 'PeopleSoft', 'vendor', '2026-02-01 02:00:00', '2026-02-01 02:15:00', 1, 'loaded'),
('b-20260129-01', 'Zycus', 'vendor', '2026-01-29 01:30:00', '2026-01-29 01:40:00', 1, 'loaded'),
('b-20251220-01', 'Spreadsheet', 'vendor', '2025-12-20 08:00:00', '2025-12-20 08:10:00', 1, 'loaded');

INSERT INTO src_peoplesoft_vendor_raw (batch_id, source_record_id, source_extract_ts, payload_json, ingested_at) VALUES
('b-20260201-01', 'ps-v-1001', '2026-02-01 02:00:00', '{"vendor_name":"Microsoft Corporation"}', '2026-02-01 02:15:00');

INSERT INTO src_zycus_vendor_raw (batch_id, source_record_id, source_extract_ts, payload_json, ingested_at) VALUES
('b-20260129-01', 'zy-v-7721', '2026-01-29 01:30:00', '{"vendor_name":"Salesforce, Inc."}', '2026-01-29 01:40:00');

INSERT INTO src_spreadsheet_vendor_raw (batch_id, source_record_id, source_extract_ts, file_name, payload_json, ingested_at) VALUES
('b-20251220-01', 'xls-row-44', '2025-12-20 08:00:00', 'legacy_vendor_import.xlsx', '{"vendor_name":"Example Legacy Vendor LLC"}', '2025-12-20 08:10:00');

INSERT INTO core_vendor (vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, source_system, source_record_id, source_batch_id, source_extract_ts, updated_at, updated_by) VALUES
('vnd-001', 'Microsoft Corporation', 'Microsoft', 'active', 'IT-ENT', 'medium', 'PeopleSoft', 'ps-v-1001', 'b-20260201-01', '2026-02-01 02:00:00', '2026-02-01 10:00:00', 'seed:system'),
('vnd-002', 'Salesforce, Inc.', 'Salesforce', 'active', 'SALES-OPS', 'low', 'Zycus', 'zy-v-7721', 'b-20260129-01', '2026-01-29 01:30:00', '2026-01-29 09:15:00', 'seed:system'),
('vnd-003', 'Example Legacy Vendor LLC', 'Legacy Vendor', 'retired', 'FIN-AP', 'high', 'Spreadsheet', 'xls-row-44', 'b-20251220-01', '2025-12-20 08:00:00', '2025-12-20 16:30:00', 'seed:system');

INSERT INTO core_vendor_identifier (vendor_identifier_id, vendor_id, identifier_type, identifier_value, is_primary, country_code, updated_at, updated_by) VALUES
('vid-001', 'vnd-001', 'duns', '123456789', 1, 'US', '2026-02-01 10:00:00', 'seed:system'),
('vid-002', 'vnd-001', 'peoplesoft_vendor_id', 'PS-1001', 0, 'US', '2026-02-01 10:00:00', 'seed:system'),
('vid-003', 'vnd-002', 'zycus_supplier_id', 'ZY-7721', 1, 'US', '2026-01-29 09:15:00', 'seed:system'),
('vid-004', 'vnd-003', 'legacy_id', 'LG-44', 1, 'US', '2025-12-20 16:30:00', 'seed:system');

INSERT INTO core_vendor_contact (vendor_contact_id, vendor_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by) VALUES
('con-001', 'vnd-001', 'account_manager', 'Alex Rivers', 'alex.rivers@example.com', '555-0101', 1, '2026-02-01 10:00:00', 'seed:system'),
('con-002', 'vnd-002', 'support', 'Jordan Lee', 'jordan.lee@example.com', '555-0142', 1, '2026-01-29 09:15:00', 'seed:system');

INSERT INTO core_vendor_org_assignment (vendor_org_assignment_id, vendor_id, org_id, assignment_type, active_flag, updated_at, updated_by) VALUES
('voa-001', 'vnd-001', 'IT-ENT', 'primary', 1, '2026-02-01 10:00:00', 'seed:system'),
('voa-002', 'vnd-001', 'SEC-OPS', 'consumer', 1, '2026-02-01 10:00:00', 'seed:system'),
('voa-003', 'vnd-002', 'SALES-OPS', 'primary', 1, '2026-01-29 09:15:00', 'seed:system'),
('voa-004', 'vnd-003', 'FIN-AP', 'primary', 0, '2025-12-20 16:30:00', 'seed:system');

INSERT INTO core_vendor_business_owner (vendor_owner_id, vendor_id, owner_user_principal, owner_role, active_flag, updated_at, updated_by) VALUES
('vown-001', 'vnd-001', 'cio-office@example.com', 'executive_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
('vown-002', 'vnd-001', 'cloud-platform@example.com', 'service_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
('vown-003', 'vnd-002', 'sales-systems@example.com', 'business_owner', 1, '2026-01-29 09:15:00', 'seed:system'),
('vown-004', 'vnd-003', 'ap-ops@example.com', 'legacy_owner', 0, '2025-12-20 16:30:00', 'seed:system');

INSERT INTO core_vendor_offering (offering_id, vendor_id, offering_name, offering_type, lob, service_type, lifecycle_state, criticality_tier, updated_at, updated_by) VALUES
('off-001', 'vnd-001', 'Microsoft 365', 'SaaS', 'Enterprise', 'Application', 'active', 'tier_1', '2026-02-01 10:00:00', 'seed:system'),
('off-002', 'vnd-001', 'Azure', 'Cloud', 'IT', 'Infrastructure', 'active', 'tier_1', '2026-02-01 10:00:00', 'seed:system'),
('off-004', 'vnd-001', 'Defender For Cloud', 'Security', 'Security', 'Security', 'in_review', 'tier_2', '2026-02-01 10:00:00', 'seed:system'),
('off-005', 'vnd-001', 'Power Platform', 'PaaS', 'Operations', 'Platform', 'approved', 'tier_2', '2026-02-01 10:00:00', 'seed:system'),
('off-006', 'vnd-001', 'Dynamics 365 Finance', 'SaaS', 'Finance', 'Application', 'retired', 'tier_3', '2026-02-01 10:00:00', 'seed:system'),
('off-003', 'vnd-002', 'Sales Cloud', 'SaaS', 'Sales', 'Application', 'active', 'tier_2', '2026-01-29 09:15:00', 'seed:system');

INSERT INTO core_offering_business_owner (offering_owner_id, offering_id, owner_user_principal, owner_role, active_flag, updated_at, updated_by) VALUES
('oown-001', 'off-001', 'workspace-admin@example.com', 'platform_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
('oown-002', 'off-002', 'cloud-architect@example.com', 'technical_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
('oown-004', 'off-004', 'security-arch@example.com', 'security_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
('oown-005', 'off-005', 'automation-lead@example.com', 'business_owner', 1, '2026-02-01 10:00:00', 'seed:system'),
('oown-006', 'off-006', 'erp-team@example.com', 'legacy_owner', 0, '2026-02-01 10:00:00', 'seed:system'),
('oown-003', 'off-003', 'salesforce-admin@example.com', 'application_owner', 1, '2026-01-29 09:15:00', 'seed:system');

INSERT INTO core_offering_contact (offering_contact_id, offering_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by) VALUES
('ocon-001', 'off-001', 'support', 'M365 Support Desk', 'm365-support@example.com', '555-2001', 1, '2026-02-01 10:00:00', 'seed:system'),
('ocon-002', 'off-002', 'escalation', 'Azure Escalation Lead', 'azure-escalation@example.com', '555-2002', 1, '2026-02-01 10:00:00', 'seed:system'),
('ocon-004', 'off-004', 'security_specialist', 'Defender Security Specialist', 'defender-security@example.com', '555-2004', 1, '2026-02-01 10:00:00', 'seed:system'),
('ocon-005', 'off-005', 'product_manager', 'Power Platform PM', 'power-platform-pm@example.com', '555-2005', 1, '2026-02-01 10:00:00', 'seed:system'),
('ocon-006', 'off-006', 'support', 'Dynamics Legacy Support', 'dynamics-legacy@example.com', '555-2006', 0, '2026-02-01 10:00:00', 'seed:system'),
('ocon-003', 'off-003', 'customer_success', 'Salesforce CSM', 'sf-csm@example.com', '555-2003', 1, '2026-01-29 09:15:00', 'seed:system');

INSERT INTO app_offering_profile (
  offering_id, vendor_id, estimated_monthly_cost, implementation_notes, data_sent, data_received,
  integration_method, inbound_method, inbound_landing_zone, inbound_identifiers, inbound_reporting_layer, inbound_ingestion_notes,
  outbound_method, outbound_creation_process, outbound_delivery_process, outbound_responsible_owner, outbound_notes,
  updated_at, updated_by
) VALUES
('off-001', 'vnd-001', 62500.00, 'M365 enterprise tenant with SSO and DLP controls.', 'license_usage, security_events', 'identity_sync, billing_status', 'api', 'api', 'raw_zone', 'tenant_id, sku_id', 'rpt_vendor_360', 'Daily API pull from Graph.', 'api', 'Automation pipeline', 'Governed delivery service', 'workspace-admin@example.com', 'Baseline profile for financial and data flow testing.', '2026-02-01 10:00:00', 'seed:system'),
('off-002', 'vnd-001', 156000.00, 'Azure landing zone with policy guardrails.', 'resource_inventory, activity_logs', 'cost_export, incident_findings', 'api', 'event_stream', 'curated_zone', 'subscription_id, resource_id', 'rpt_vendor_360', 'Ingested via scheduled export.', 'sftp', 'Nightly batch build', 'Secure file transfer', 'cloud-architect@example.com', 'Cost and security streams enabled.', '2026-02-01 10:00:00', 'seed:system'),
('off-003', 'vnd-002', 84200.00, 'Sales Cloud CRM deployment for regional sales teams.', 'pipeline_changes, account_updates', 'billing_events, support_metrics', 'api', 'api', 'raw_zone', 'org_id, opportunity_id', 'rpt_vendor_360', 'Near real-time webhook ingest.', 'api', 'Streaming transformation', 'REST push to downstream systems', 'salesforce-admin@example.com', 'Includes quarterly usage true-up.', '2026-01-29 09:15:00', 'seed:system'),
('off-004', 'vnd-001', 42500.00, 'Defender workloads scoped for critical systems.', 'threat_events, endpoint_alerts', 'case_updates, policy_changes', 'api', 'api', 'raw_zone', 'device_id, alert_id', 'rpt_vendor_demo_outcomes', 'SIEM-aligned normalization logic.', 'api', 'Security orchestration workflow', 'SOC dashboard export', 'security-arch@example.com', 'High-frequency security integration.', '2026-02-01 10:00:00', 'seed:system'),
('off-005', 'vnd-001', 28900.00, 'Power Platform workflow automations and governance.', 'flow_runs, app_telemetry', 'license_position, incidents', 'api', 'api', 'curated_zone', 'environment_id, flow_id', 'rpt_vendor_360', 'Imported through managed connector.', 'api', 'Power BI semantic model refresh', 'Executive reporting feed', 'automation-lead@example.com', 'Supports operational automation reporting.', '2026-02-01 10:00:00', 'seed:system'),
('off-006', 'vnd-001', 17300.00, 'Legacy Dynamics footprint retained for archive access.', 'invoice_archive, account_changes', 'deprecation_notices', 'manual', 'sftp', 'archive_zone', 'customer_id, document_id', 'rpt_contract_cancellations', 'Manual ingest during retirement phase.', 'manual', 'Controlled archival procedure', 'Manual delivery to archive teams', 'erp-team@example.com', 'Retired but maintained for historical validation.', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_offering_data_flow (
  data_flow_id, offering_id, vendor_id, direction, flow_name, method, data_description, endpoint_details,
  identifiers, reporting_layer, creation_process, delivery_process, owner_user_principal, notes,
  active_flag, created_at, created_by, updated_at, updated_by
) VALUES
('flow-001-in', 'off-001', 'vnd-001', 'inbound', 'M365 Inbound Usage Feed', 'api', 'License usage and tenant health.', 'https://graph.microsoft.com/v1.0/reports', 'tenant_id, sku_id', 'rpt_vendor_360', NULL, NULL, 'workspace-admin@example.com', 'Validated daily.', 1, '2026-01-20 08:00:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system'),
('flow-001-out', 'off-001', 'vnd-001', 'outbound', 'M365 Outbound Compliance Feed', 'api', 'Compliance posture summary.', 'https://api.internal.example.com/compliance/m365', 'tenant_id, compliance_profile', 'rpt_vendor_360', 'Compliance extract build', 'API publish', 'workspace-admin@example.com', 'Shared with security operations.', 1, '2026-01-20 08:10:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system'),
('flow-002-in', 'off-002', 'vnd-001', 'inbound', 'Azure Cost Export', 'sftp', 'Daily cloud spend export.', 'sftp://finance-storage.example.com/azure', 'subscription_id, cost_center', 'rpt_vendor_360', NULL, NULL, 'cloud-architect@example.com', 'Primary financial feed.', 1, '2026-01-21 07:00:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system'),
('flow-003-in', 'off-003', 'vnd-002', 'inbound', 'Salesforce Pipeline Webhook', 'api', 'Opportunity and account changes.', 'https://hooks.salesforce.example.com/pipeline', 'opportunity_id, account_id', 'rpt_vendor_360', NULL, NULL, 'salesforce-admin@example.com', 'Supports project and demo alignment.', 1, '2026-01-23 10:00:00', 'seed:system', '2026-01-29 09:15:00', 'seed:system'),
('flow-004-in', 'off-004', 'vnd-001', 'inbound', 'Defender Alert Stream', 'api', 'Security alert telemetry.', 'https://api.security.microsoft.com/alerts', 'device_id, alert_id', 'rpt_vendor_demo_outcomes', NULL, NULL, 'security-arch@example.com', 'Feeds SOC triage queue.', 1, '2026-01-24 06:00:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system'),
('flow-005-in', 'off-005', 'vnd-001', 'inbound', 'Power Platform Usage Feed', 'api', 'Flow and app usage events.', 'https://api.powerplatform.example.com/usage', 'environment_id, flow_id', 'rpt_vendor_360', NULL, NULL, 'automation-lead@example.com', 'Used for automation ROI reporting.', 1, '2026-01-25 09:00:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system');

INSERT INTO app_offering_ticket (
  ticket_id, offering_id, vendor_id, ticket_system, external_ticket_id, title, status, priority,
  opened_date, closed_date, notes, active_flag, created_at, created_by, updated_at, updated_by
) VALUES
('tkt-001', 'off-001', 'vnd-001', 'ServiceNow', 'INC300001', 'M365 tenant DLP policy update', 'resolved', 'medium', '2026-01-08', '2026-01-11', 'Policy update completed.', 1, '2026-01-08 09:00:00', 'seed:system', '2026-01-11 16:30:00', 'seed:system'),
('tkt-002', 'off-002', 'vnd-001', 'ServiceNow', 'INC300118', 'Azure budget alert tuning', 'in_progress', 'high', '2026-01-19', NULL, 'Awaiting final thresholds from finance.', 1, '2026-01-19 08:30:00', 'seed:system', '2026-02-01 10:00:00', 'seed:system'),
('tkt-003', 'off-003', 'vnd-002', 'Jira', 'CRM-4472', 'Sales Cloud profile sync issue', 'open', 'high', '2026-01-28', NULL, 'Intermittent profile mismatch observed.', 1, '2026-01-28 11:15:00', 'seed:system', '2026-01-29 09:15:00', 'seed:system'),
('tkt-004', 'off-004', 'vnd-001', 'ServiceNow', 'INC300244', 'Defender endpoint false positives', 'resolved', 'medium', '2026-01-30', '2026-02-02', 'Rule tuning deployed.', 1, '2026-01-30 10:00:00', 'seed:system', '2026-02-02 13:20:00', 'seed:system');

INSERT INTO app_offering_invoice (
  invoice_id, offering_id, vendor_id, invoice_number, invoice_date, amount, currency_code, invoice_status, notes,
  active_flag, created_at, created_by, updated_at, updated_by
) VALUES
('inv-001', 'off-001', 'vnd-001', 'MS365-2026-01', '2026-01-31', 62880.00, 'USD', 'paid', 'January M365 billing cycle.', 1, '2026-02-01 09:00:00', 'seed:system', '2026-02-03 09:00:00', 'seed:system'),
('inv-002', 'off-001', 'vnd-001', 'MS365-2025-12', '2025-12-31', 62110.00, 'USD', 'paid', 'December M365 billing cycle.', 1, '2026-01-01 09:00:00', 'seed:system', '2026-01-03 09:00:00', 'seed:system'),
('inv-003', 'off-002', 'vnd-001', 'AZR-2026-01', '2026-01-31', 159200.00, 'USD', 'approved', 'Azure enterprise consumption.', 1, '2026-02-01 08:00:00', 'seed:system', '2026-02-02 11:00:00', 'seed:system'),
('inv-004', 'off-003', 'vnd-002', 'SF-2026-01', '2026-01-31', 84750.00, 'USD', 'pending', 'Sales Cloud annualized invoice tranche.', 1, '2026-02-01 08:15:00', 'seed:system', '2026-02-03 08:45:00', 'seed:system'),
('inv-005', 'off-004', 'vnd-001', 'DEF-2026-01', '2026-01-31', 42980.00, 'USD', 'paid', 'Defender subscription billing.', 1, '2026-02-01 08:20:00', 'seed:system', '2026-02-03 09:10:00', 'seed:system'),
('inv-006', 'off-005', 'vnd-001', 'PWR-2026-01', '2026-01-31', 29120.00, 'USD', 'approved', 'Power Platform licensing and support.', 1, '2026-02-01 08:25:00', 'seed:system', '2026-02-03 09:15:00', 'seed:system');

INSERT INTO core_contract (contract_id, vendor_id, offering_id, contract_number, contract_status, start_date, end_date, cancelled_flag, annual_value, updated_at, updated_by) VALUES
('ctr-101', 'vnd-001', 'off-002', 'MS-2024-001', 'active', '2024-04-01', '2026-03-15', 0, 1880000.0, '2026-02-01 10:00:00', 'seed:system'),
('ctr-102', 'vnd-001', 'off-001', 'MS-2024-002', 'active', '2024-02-01', '2026-06-30', 0, 720000.0, '2026-02-01 10:00:00', 'seed:system'),
('ctr-103', 'vnd-001', 'off-006', 'MS-2022-010', 'retired', '2022-01-01', '2025-09-30', 1, 0.0, '2026-02-01 10:00:00', 'seed:system'),
('ctr-202', 'vnd-002', 'off-003', 'SF-2024-210', 'active', '2024-06-01', '2026-04-01', 0, 745000.0, '2026-01-29 09:15:00', 'seed:system'),
('ctr-001', 'vnd-003', NULL, 'LG-2022-005', 'cancelled', '2022-01-01', '2025-12-05', 1, 0.0, '2025-12-20 16:30:00', 'seed:system');

INSERT INTO core_contract_event (contract_event_id, contract_id, event_type, event_ts, reason_code, notes, actor_user_principal) VALUES
('ce-001', 'ctr-101', 'renewal_planned', '2026-01-05 09:00:00', NULL, 'Preparing renewal proposal.', 'procurement@example.com'),
('ce-004', 'ctr-102', 'renewal_planned', '2026-01-18 10:00:00', NULL, 'Renewal package shared for review.', 'procurement@example.com'),
('ce-005', 'ctr-103', 'contract_cancelled', '2025-09-30 14:30:00', 'product_consolidation', 'Consolidated into newer stack.', 'it-ops@example.com'),
('ce-002', 'ctr-202', 'renewal_negotiation', '2026-01-12 11:30:00', NULL, 'Negotiation round 1.', 'sourcing@example.com'),
('ce-003', 'ctr-001', 'contract_cancelled', '2025-12-05 13:00:00', 'cost_overrun', 'Renewal cost exceeded target.', 'fin-ops@example.com');

INSERT INTO core_vendor_demo (demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes, updated_at, updated_by) VALUES
('demo-001', 'vnd-001', 'off-002', '2026-01-10', 8.9, 'selected', NULL, 'Strong security and integration.', '2026-01-10 15:00:00', 'seed:system'),
('demo-003', 'vnd-001', 'off-004', '2026-01-28', 6.1, 'not_selected', 'insufficient_coverage', 'Did not meet advanced detection requirements.', '2026-01-28 16:20:00', 'seed:system'),
('demo-004', 'vnd-001', 'off-005', '2026-02-02', 6.8, 'not_selected', 'cost_overrun', 'Total cost of ownership exceeded approved budget.', '2026-02-02 17:05:00', 'seed:system'),
('demo-005', 'vnd-001', 'off-006', '2025-07-10', 5.4, 'deferred', 'roadmap_uncertain', 'Deferred pending roadmap clarification.', '2025-07-10 12:45:00', 'seed:system'),
('demo-002', 'vnd-003', NULL, '2025-11-01', 5.2, 'not_selected', 'poor_scalability', 'Failed on scale testing.', '2025-11-01 16:00:00', 'seed:system');

INSERT INTO core_vendor_demo_score (demo_score_id, demo_id, score_category, score_value, weight, comments) VALUES
('ds-001', 'demo-001', 'security', 9.1, 0.3, 'Strong controls.'),
('ds-002', 'demo-001', 'integration', 8.8, 0.25, 'Good integration patterns.'),
('ds-003', 'demo-001', 'cost', 8.2, 0.2, 'Competitive with enterprise discount.'),
('ds-006', 'demo-003', 'coverage', 5.2, 0.3, 'Coverage gaps in key use cases.'),
('ds-007', 'demo-003', 'integration', 6.5, 0.2, 'Adequate integration path.'),
('ds-008', 'demo-004', 'cost', 4.7, 0.35, 'Budget exceeded target range.'),
('ds-009', 'demo-004', 'business_fit', 7.1, 0.25, 'Good fit but too expensive.'),
('ds-010', 'demo-005', 'roadmap', 5.0, 0.3, 'Roadmap uncertainty for requirements.'),
('ds-004', 'demo-002', 'scalability', 4.9, 0.35, 'Could not meet throughput target.'),
('ds-005', 'demo-002', 'ux', 6.0, 0.15, 'Usable but dated.');

INSERT INTO core_vendor_demo_note (demo_note_id, demo_id, note_type, note_text, created_at, created_by) VALUES
('dn-001', 'demo-001', 'selection_rationale', 'Selected due to security baseline and integration maturity.', '2026-01-10 15:00:00', 'architecture-board@example.com'),
('dn-003', 'demo-003', 'non_selection_rationale', 'Coverage gaps against SOC monitoring and response criteria.', '2026-01-28 16:20:00', 'security-board@example.com'),
('dn-004', 'demo-004', 'non_selection_rationale', 'Not selected due to budget and duplicate capability overlap.', '2026-02-02 17:05:00', 'procurement-board@example.com'),
('dn-005', 'demo-005', 'defer_rationale', 'Deferred pending roadmap commitment from vendor.', '2025-07-10 12:45:00', 'architecture-board@example.com'),
('dn-002', 'demo-002', 'non_selection_rationale', 'Rejected due to poor scalability and uncertain roadmap.', '2025-11-01 16:00:00', 'architecture-board@example.com');

INSERT INTO app_vendor_change_request (change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at) VALUES
('cr-001', 'vnd-001', 'cloud-platform@example.com', 'update_contact', '{"contact":"new escalation"}', 'approved', '2026-01-15 10:00:00', '2026-01-16 09:00:00'),
('cr-002', 'vnd-001', 'procurement@example.com', 'request_lifecycle_change', '{"state":"active"}', 'submitted', '2026-02-03 10:30:00', '2026-02-03 10:30:00'),
('cr-003', 'vnd-003', 'fin-ops@example.com', 'update_vendor_profile', '{"risk_tier":"high"}', 'approved', '2025-12-19 08:15:00', '2025-12-20 09:45:00');

INSERT INTO change_request (request_id, entity_type, entity_id, change_type, payload_json, request_status, created_at, created_by) VALUES
('cr-001', 'vendor', 'vnd-001', 'update_contact', '{"contact":"new escalation"}', 'approved', '2026-01-15 10:00:00', 'cloud-platform@example.com'),
('cr-002', 'vendor', 'vnd-001', 'request_lifecycle_change', '{"state":"active"}', 'submitted', '2026-02-03 10:30:00', 'procurement@example.com'),
('cr-003', 'vendor', 'vnd-003', 'update_vendor_profile', '{"risk_tier":"high"}', 'approved', '2025-12-19 08:15:00', 'fin-ops@example.com');

INSERT INTO app_project (project_id, vendor_id, project_name, project_type, status, start_date, target_date, owner_principal, description, active_flag, created_at, created_by, updated_at, updated_by) VALUES
('prj-001', 'vnd-001', 'Defender Rollout FY26', 'implementation', 'active', '2026-01-05', '2026-06-30', 'bob.smith@example.com', 'Expand Defender controls across core workloads.', 1, '2026-01-05 09:00:00', 'admin@example.com', '2026-02-01 14:00:00', 'admin@example.com'),
('prj-002', 'vnd-001', 'Power Platform Evaluation', 'poc', 'blocked', '2026-01-20', '2026-03-31', 'amy.johnson@example.com', 'Evaluate business automation use cases.', 1, '2026-01-20 11:00:00', 'admin@example.com', '2026-02-03 10:30:00', 'admin@example.com');

INSERT INTO app_project_vendor_map (project_vendor_map_id, project_id, vendor_id, active_flag, created_at, created_by, updated_at, updated_by) VALUES
('pvm-001', 'prj-001', 'vnd-001', 1, '2026-01-05 09:00:00', 'admin@example.com', '2026-01-05 09:00:00', 'admin@example.com'),
('pvm-002', 'prj-002', 'vnd-001', 1, '2026-01-20 11:00:00', 'admin@example.com', '2026-01-20 11:00:00', 'admin@example.com');

INSERT INTO app_project_offering_map (project_offering_map_id, project_id, vendor_id, offering_id, active_flag, created_at, created_by, updated_at, updated_by) VALUES
('pom-001', 'prj-001', 'vnd-001', 'off-004', 1, '2026-01-05 09:00:00', 'admin@example.com', '2026-01-05 09:00:00', 'admin@example.com'),
('pom-002', 'prj-001', 'vnd-001', 'off-002', 1, '2026-01-05 09:00:00', 'admin@example.com', '2026-01-05 09:00:00', 'admin@example.com'),
('pom-003', 'prj-002', 'vnd-001', 'off-005', 1, '2026-01-20 11:00:00', 'admin@example.com', '2026-01-20 11:00:00', 'admin@example.com');

INSERT INTO app_project_demo (project_demo_id, project_id, vendor_id, demo_name, demo_datetime_start, demo_datetime_end, demo_type, outcome, score, attendees_internal, attendees_vendor, notes, followups, linked_offering_id, linked_vendor_demo_id, active_flag, created_at, created_by, updated_at, updated_by) VALUES
('pdm-001', 'prj-001', 'vnd-001', 'Defender Deep Dive', '2026-01-28 13:00:00', '2026-01-28 14:30:00', 'workshop', 'follow_up', 7.4, 'security team; architecture', 'defender specialists', 'Need additional endpoint coverage details.', 'Review roadmap in next session.', 'off-004', 'demo-003', 1, '2026-01-28 15:00:00', 'admin@example.com', '2026-01-28 15:00:00', 'admin@example.com');

INSERT INTO app_project_note (project_note_id, project_id, vendor_id, note_text, active_flag, created_at, created_by, updated_at, updated_by) VALUES
('pnt-001', 'prj-001', 'vnd-001', 'Initial kickoff complete; pending ownership confirmation.', 1, '2026-02-01 09:30:00', 'admin@example.com', '2026-02-01 09:30:00', 'admin@example.com');

INSERT INTO app_document_link (doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, active_flag, created_at, created_by, updated_at, updated_by) VALUES
('doc-001', 'vendor', 'vnd-001', 'sharepoint.com - Vendor_Master_Packet.pdf', 'https://contoso.sharepoint.com/sites/vendor/Documents/Vendor_Master_Packet.pdf', 'sharepoint', 'master,contract', 'procurement@example.com', 1, '2026-01-18 10:00:00', 'admin@example.com', '2026-01-18 10:00:00', 'admin@example.com'),
('doc-002', 'project', 'prj-001', 'confluence - Defender-Rollout-Notes', 'https://example.atlassian.net/wiki/spaces/SEC/pages/12345/Defender-Rollout-Notes', 'confluence', 'notes', 'bob.smith@example.com', 1, '2026-01-29 09:15:00', 'admin@example.com', '2026-01-29 09:15:00', 'admin@example.com'),
('doc-003', 'offering', 'off-004', 'github.com - threat-model.md', 'https://github.com/example/security-docs/blob/main/threat-model.md', 'github', 'security,architecture', 'security-arch@example.com', 1, '2026-01-30 08:00:00', 'admin@example.com', '2026-01-30 08:00:00', 'admin@example.com');

INSERT INTO audit_entity_change (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id) VALUES
('ae-001', 'core_vendor', 'vnd-001', 'update', NULL, NULL, 'vendor_steward@example.com', '2026-01-16 09:00:00', 'cr-001'),
('ae-002', 'core_vendor_demo', 'demo-002', 'insert', NULL, NULL, 'architecture-board@example.com', '2025-11-01 16:00:00', NULL),
('ae-003', 'core_contract', 'ctr-001', 'update', NULL, NULL, 'fin-ops@example.com', '2025-12-05 13:00:00', NULL);

INSERT INTO app_usage_log (usage_event_id, user_principal, page_name, event_type, event_ts, payload_json) VALUES
('use-001', 'admin@example.com', 'vendor_360', 'page_view', '2026-02-03 08:00:00', '{"section":"list"}'),
('use-002', 'bob.smith@example.com', 'project_detail', 'page_view', '2026-02-03 09:10:00', '{"project_id":"prj-001"}');

INSERT INTO app_access_request (access_request_id, requester_user_principal, requested_role, justification, status, submitted_at, updated_at) VALUES
('ar-001', 'analyst@example.com', 'vendor_viewer', 'Need read-only access for monthly reporting.', 'pending', '2026-02-02 09:00:00', '2026-02-02 09:00:00'),
('ar-002', 'editor@example.com', 'vendor_editor', 'Support vendor data maintenance.', 'approved', '2026-01-28 13:00:00', '2026-01-29 08:00:00');

INSERT INTO app_onboarding_request (request_id, requestor_user_principal, vendor_name_raw, priority, status, submitted_at, updated_at) VALUES
('onb-001', 'procurement@example.com', 'Contoso Managed Services', 'high', 'in_review', '2026-02-01 10:00:00', '2026-02-03 09:00:00'),
('onb-002', 'bob.smith@example.com', 'Fabrikam Security', 'medium', 'submitted', '2026-02-03 08:30:00', '2026-02-03 08:30:00');

INSERT INTO app_onboarding_task (task_id, request_id, task_type, assignee_group, due_at, status, updated_at, updated_by) VALUES
('task-001', 'onb-001', 'risk_review', 'group:corp_security', '2026-02-08 17:00:00', 'open', '2026-02-03 09:00:00', 'procurement@example.com'),
('task-002', 'onb-001', 'legal_review', 'group:corp_finance', '2026-02-10 17:00:00', 'in_progress', '2026-02-03 09:10:00', 'procurement@example.com');

INSERT INTO app_onboarding_approval (approval_id, request_id, stage_name, approver_user_principal, decision, decided_at, comments, updated_at) VALUES
('apr-001', 'onb-001', 'security', 'security-arch@example.com', 'approved', '2026-02-03 10:00:00', 'Security controls meet baseline.', '2026-02-03 10:00:00'),
('apr-002', 'onb-001', 'finance', 'procurement@example.com', 'pending', NULL, 'Pending pricing validation.', '2026-02-03 10:15:00');

INSERT INTO app_user_settings (setting_id, user_principal, setting_key, setting_value_json, updated_at, updated_by) VALUES
('set-001', 'admin@example.com', 'vendor360_list', '{"filters":{"lifecycle_state":"active"},"sort_by":"display_name","sort_dir":"asc"}', '2026-02-03 10:00:00', 'admin@example.com'),
('set-002', 'bob.smith@example.com', 'vendor360_list', '{"filters":{"risk_tier":"high"},"sort_by":"updated_at","sort_dir":"desc"}', '2026-02-03 10:05:00', 'bob.smith@example.com');

INSERT INTO app_note (note_id, entity_name, entity_id, note_type, note_text, created_at, created_by) VALUES
('note-001', 'vendor', 'vnd-001', 'governance_note', 'Quarterly business review completed and documented.', '2026-02-02 15:00:00', 'admin@example.com'),
('note-002', 'contract', 'ctr-101', 'finance_note', 'Renewal negotiations include uplift cap at 3 percent.', '2026-02-03 11:00:00', 'procurement@example.com');

INSERT INTO hist_vendor (vendor_hist_id, vendor_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason) VALUES
('hvend-001', 'vnd-001', 1, '2025-01-01 00:00:00', NULL, 1, '{"vendor_id":"vnd-001","display_name":"Microsoft","risk_tier":"medium"}', 'seed:system', 'initial_seed'),
('hvend-002', 'vnd-002', 1, '2025-01-01 00:00:00', NULL, 1, '{"vendor_id":"vnd-002","display_name":"Salesforce","risk_tier":"low"}', 'seed:system', 'initial_seed');

INSERT INTO hist_vendor_offering (vendor_offering_hist_id, offering_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason) VALUES
('hoff-001', 'off-001', 1, '2025-01-01 00:00:00', NULL, 1, '{"offering_id":"off-001","offering_name":"Microsoft 365","lifecycle_state":"active"}', 'seed:system', 'initial_seed'),
('hoff-002', 'off-003', 1, '2025-01-01 00:00:00', NULL, 1, '{"offering_id":"off-003","offering_name":"Sales Cloud","lifecycle_state":"active"}', 'seed:system', 'initial_seed');

INSERT INTO hist_contract (contract_hist_id, contract_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason) VALUES
('hctr-001', 'ctr-101', 1, '2024-04-01 00:00:00', NULL, 1, '{"contract_id":"ctr-101","contract_status":"active","annual_value":1880000.0}', 'seed:system', 'initial_seed'),
('hctr-002', 'ctr-202', 1, '2024-06-01 00:00:00', NULL, 1, '{"contract_id":"ctr-202","contract_status":"active","annual_value":745000.0}', 'seed:system', 'initial_seed');

INSERT INTO audit_workflow_event (workflow_event_id, workflow_type, workflow_id, old_status, new_status, actor_user_principal, event_ts, notes) VALUES
('awf-001', 'onboarding_request', 'onb-001', 'submitted', 'in_review', 'procurement@example.com', '2026-02-03 09:00:00', 'Security and finance reviews initiated.'),
('awf-002', 'access_request', 'ar-001', 'submitted', 'pending', 'admin@example.com', '2026-02-02 09:30:00', 'Awaiting approver decision.');

INSERT INTO audit_access_event (access_event_id, actor_user_principal, action_type, target_user_principal, target_role, event_ts, notes) VALUES
('aac-001', 'admin@example.com', 'grant_role', 'editor@example.com', 'vendor_editor', '2026-01-29 08:00:00', 'Approved editor access.'),
('aac-002', 'admin@example.com', 'grant_scope', 'editor@example.com', NULL, '2026-01-29 08:05:00', 'Scoped to sales operations.');

INSERT INTO app_employee_directory (login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag) VALUES
('admin@example.com', 'admin@example.com', 'admin', 'E1001', 'E1000', 'Admin', 'User', 'Admin User', 1),
('bob.smith@example.com', 'bob.smith@example.com', 'bsmith', 'E1002', 'E1001', 'Bob', 'Smith', 'Bob Smith', 1),
('amy.johnson@example.com', 'amy.johnson@example.com', 'ajohnson', 'E1003', 'E1001', 'Amy', 'Johnson', 'Amy Johnson', 1),
('procurement@example.com', 'procurement@example.com', 'procurement', 'E1004', 'E1001', 'Procurement', 'Team', 'Procurement Team', 1),
('security-arch@example.com', 'security-arch@example.com', 'secarch', 'E1005', 'E1001', 'Security', 'Architect', 'Security Architect', 1),
('cloud-platform@example.com', 'cloud-platform@example.com', 'cloudplat', 'E1006', 'E1001', 'Cloud', 'Platform', 'Cloud Platform', 1),
('sales-systems@example.com', 'sales-systems@example.com', 'salessys', 'E1007', 'E1001', 'Sales', 'Systems', 'Sales Systems', 1),
('pm@example.com', 'pm@example.com', 'projmgr', 'E1008', 'E1001', 'Project', 'Manager', 'Project Manager', 1),
('secops@example.com', 'secops@example.com', 'secops', 'E1009', 'E1001', 'SecOps', 'User', 'Secops User', 1),
('owner@example.com', 'owner@example.com', 'owner', 'E1010', 'E1001', 'Owner', 'User', 'Owner User', 1);

INSERT OR REPLACE INTO app_user_directory (user_id, login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag, created_at, updated_at, last_seen_at) VALUES
('usr-001', 'admin@example.com', 'admin@example.com', 'admin', 'E1001', 'E1000', 'Admin', 'User', 'Admin User', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-002', 'bob.smith@example.com', 'bob.smith@example.com', 'bsmith', 'E1002', 'E1001', 'Bob', 'Smith', 'Bob Smith', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-003', 'amy.johnson@example.com', 'amy.johnson@example.com', 'ajohnson', 'E1003', 'E1001', 'Amy', 'Johnson', 'Amy Johnson', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-004', 'procurement@example.com', 'procurement@example.com', 'procurement', 'E1004', 'E1001', 'Procurement', 'Team', 'Procurement Team', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-005', 'security-arch@example.com', 'security-arch@example.com', 'secarch', 'E1005', 'E1001', 'Security', 'Architect', 'Security Architect', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-006', 'cloud-platform@example.com', 'cloud-platform@example.com', 'cloudplat', 'E1006', 'E1001', 'Cloud', 'Platform', 'Cloud Platform', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-007', 'sales-systems@example.com', 'sales-systems@example.com', 'salessys', 'E1007', 'E1001', 'Sales', 'Systems', 'Sales Systems', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-008', 'pm@example.com', 'pm@example.com', 'projmgr', 'E1008', 'E1001', 'Project', 'Manager', 'Project Manager', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-009', 'secops@example.com', 'secops@example.com', 'secops', 'E1009', 'E1001', 'SecOps', 'User', 'Secops User', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00'),
('usr-010', 'owner@example.com', 'owner@example.com', 'owner', 'E1010', 'E1001', 'Owner', 'User', 'Owner User', 1, '2026-01-01 00:00:00', '2026-02-03 10:00:00', '2026-02-03 10:00:00');

INSERT INTO app_lookup_option (option_id, lookup_type, option_code, option_label, sort_order, active_flag, valid_from_ts, valid_to_ts, is_current, deleted_flag, updated_at, updated_by) VALUES
('lkp-doc_source-sharepoint', 'doc_source', 'sharepoint', 'Sharepoint', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-onedrive', 'doc_source', 'onedrive', 'Onedrive', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-confluence', 'doc_source', 'confluence', 'Confluence', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-google_drive', 'doc_source', 'google_drive', 'Google Drive', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-box', 'doc_source', 'box', 'Box', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-dropbox', 'doc_source', 'dropbox', 'Dropbox', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-github', 'doc_source', 'github', 'Github', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_source-other', 'doc_source', 'other', 'Other', 8, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-contract', 'doc_tag', 'contract', 'Contract', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-msa', 'doc_tag', 'msa', 'Msa', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-nda', 'doc_tag', 'nda', 'Nda', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-sow', 'doc_tag', 'sow', 'Sow', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-invoice', 'doc_tag', 'invoice', 'Invoice', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-renewal', 'doc_tag', 'renewal', 'Renewal', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-security', 'doc_tag', 'security', 'Security', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-architecture', 'doc_tag', 'architecture', 'Architecture', 8, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-runbook', 'doc_tag', 'runbook', 'Runbook', 9, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-compliance', 'doc_tag', 'compliance', 'Compliance', 10, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-rfp', 'doc_tag', 'rfp', 'Rfp', 11, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-poc', 'doc_tag', 'poc', 'Poc', 12, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-notes', 'doc_tag', 'notes', 'Notes', 13, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-operations', 'doc_tag', 'operations', 'Operations', 14, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-doc_tag-folder', 'doc_tag', 'folder', 'Folder', 15, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-business_owner', 'owner_role', 'business_owner', 'Business Owner', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-executive_owner', 'owner_role', 'executive_owner', 'Executive Owner', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-service_owner', 'owner_role', 'service_owner', 'Service Owner', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-technical_owner', 'owner_role', 'technical_owner', 'Technical Owner', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-security_owner', 'owner_role', 'security_owner', 'Security Owner', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-application_owner', 'owner_role', 'application_owner', 'Application Owner', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-platform_owner', 'owner_role', 'platform_owner', 'Platform Owner', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-owner_role-legacy_owner', 'owner_role', 'legacy_owner', 'Legacy Owner', 8, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-assignment_type-consumer', 'assignment_type', 'consumer', 'Consumer', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-assignment_type-primary', 'assignment_type', 'primary', 'Primary', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-assignment_type-secondary', 'assignment_type', 'secondary', 'Secondary', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-business', 'contact_type', 'business', 'Business', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-account_manager', 'contact_type', 'account_manager', 'Account Manager', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-support', 'contact_type', 'support', 'Support', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-escalation', 'contact_type', 'escalation', 'Escalation', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-security_specialist', 'contact_type', 'security_specialist', 'Security Specialist', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-customer_success', 'contact_type', 'customer_success', 'Customer Success', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-contact_type-product_manager', 'contact_type', 'product_manager', 'Product Manager', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-project_type-rfp', 'project_type', 'rfp', 'RFP', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-project_type-poc', 'project_type', 'poc', 'PoC', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-project_type-renewal', 'project_type', 'renewal', 'Renewal', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-project_type-implementation', 'project_type', 'implementation', 'Implementation', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-project_type-other', 'project_type', 'other', 'Other', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-saas', 'offering_type', 'saas', 'SaaS', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-cloud', 'offering_type', 'cloud', 'Cloud', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-paas', 'offering_type', 'paas', 'PaaS', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-security', 'offering_type', 'security', 'Security', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-data', 'offering_type', 'data', 'Data', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-integration', 'offering_type', 'integration', 'Integration', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_type-other', 'offering_type', 'other', 'Other', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-enterprise', 'offering_lob', 'enterprise', 'Enterprise', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-finance', 'offering_lob', 'finance', 'Finance', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-hr', 'offering_lob', 'hr', 'HR', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-it', 'offering_lob', 'it', 'IT', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-operations', 'offering_lob', 'operations', 'Operations', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-sales', 'offering_lob', 'sales', 'Sales', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_lob-security', 'offering_lob', 'security', 'Security', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-application', 'offering_service_type', 'application', 'Application', 1, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-infrastructure', 'offering_service_type', 'infrastructure', 'Infrastructure', 2, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-integration', 'offering_service_type', 'integration', 'Integration', 3, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-managed_service', 'offering_service_type', 'managed_service', 'Managed Service', 4, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-platform', 'offering_service_type', 'platform', 'Platform', 5, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-security', 'offering_service_type', 'security', 'Security', 6, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-support', 'offering_service_type', 'support', 'Support', 7, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap'),
('lkp-offering_service_type-other', 'offering_service_type', 'other', 'Other', 8, 1, '2026-01-01 00:00:00', NULL, 1, 0, '2026-01-01 00:00:00', 'bootstrap');

INSERT OR REPLACE INTO sec_role_definition (role_code, role_name, description, approval_level, can_edit, can_report, can_direct_apply, active_flag, updated_at, updated_by) VALUES
('vendor_admin', 'Vendor Admin', 'Full administrative access across all workflows and data changes.', 3, 1, 1, 1, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_steward', 'Vendor Steward', 'Data steward with elevated review/apply rights for governed updates.', 2, 1, 1, 1, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_editor', 'Vendor Editor', 'Contributor role for day-to-day edits and change submissions.', 1, 1, 1, 0, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_viewer', 'Vendor Viewer', 'Read-only access to vendor inventory and metadata.', 0, 0, 0, 0, 1, '2026-01-01 00:00:00', 'bootstrap'),
('vendor_auditor', 'Vendor Auditor', 'Read/report access for governance and audit functions.', 0, 0, 1, 0, 1, '2026-01-01 00:00:00', 'bootstrap');

INSERT INTO sec_role_permission (role_code, object_name, action_code, active_flag, updated_at) VALUES
('vendor_admin', 'change_action', 'create_vendor_profile', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'update_vendor_profile', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'update_offering', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'create_offering', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'create_contract', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'update_contract', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'map_contract_to_offering', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'map_demo_to_offering', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'add_offering_owner', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'remove_offering_owner', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'add_offering_contact', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'remove_offering_contact', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'create_project', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'update_project', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'update_project_owner', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'attach_project_vendor', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'attach_project_offering', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'add_project_note', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'create_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'update_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'remove_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'create_doc_link', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'remove_doc_link', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'create_demo_outcome', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'record_contract_cancellation', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'grant_role', 1, '2026-01-01 00:00:00'),
('vendor_admin', 'change_action', 'grant_scope', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'update_vendor_profile', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'update_offering', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'create_offering', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'create_contract', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'update_contract', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'map_contract_to_offering', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'map_demo_to_offering', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'add_offering_owner', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'remove_offering_owner', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'add_offering_contact', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'remove_offering_contact', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'create_project', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'update_project', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'update_project_owner', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'attach_project_vendor', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'attach_project_offering', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'add_project_note', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'create_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'update_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'remove_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'create_doc_link', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'remove_doc_link', 1, '2026-01-01 00:00:00'),
('vendor_steward', 'change_action', 'create_demo_outcome', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'map_demo_to_offering', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'add_offering_contact', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'remove_offering_contact', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'add_project_note', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'update_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'remove_project_demo', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'create_doc_link', 1, '2026-01-01 00:00:00'),
('vendor_editor', 'change_action', 'remove_doc_link', 1, '2026-01-01 00:00:00');

INSERT INTO sec_user_role_map (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at) VALUES
('admin@example.com', 'vendor_admin', 1, 'bootstrap', '2026-01-01 00:00:00', NULL),
('editor@example.com', 'vendor_editor', 1, 'admin@example.com', '2026-01-15 08:00:00', NULL),
('viewer@example.com', 'vendor_viewer', 1, 'admin@example.com', '2026-01-20 09:00:00', NULL);

INSERT INTO sec_group_role_map (group_principal, role_code, active_flag, granted_by, granted_at, revoked_at) VALUES
('group:corp_security', 'vendor_auditor', 1, 'bootstrap', '2026-01-01 00:00:00', NULL),
('group:corp_procurement', 'vendor_steward', 1, 'bootstrap', '2026-01-01 00:00:00', NULL);

INSERT INTO sec_user_org_scope (user_principal, org_id, scope_level, active_flag, granted_at) VALUES
('admin@example.com', 'IT-ENT', 'full', 1, '2026-01-01 00:00:00'),
('editor@example.com', 'SALES-OPS', 'edit', 1, '2026-01-15 08:00:00');

COMMIT;


