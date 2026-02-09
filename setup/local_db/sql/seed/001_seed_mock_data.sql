PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Reset seeded entities so running seed multiple times stays deterministic.
DELETE FROM app_project_note;
DELETE FROM app_project_demo;
DELETE FROM app_project_offering_map;
DELETE FROM app_project_vendor_map;
DELETE FROM app_project;
DELETE FROM app_document_link;
DELETE FROM app_vendor_change_request;
DELETE FROM app_note;
DELETE FROM app_usage_log;
DELETE FROM app_user_settings;
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

INSERT INTO core_vendor_offering (offering_id, vendor_id, offering_name, offering_type, lifecycle_state, criticality_tier, updated_at, updated_by) VALUES
('off-001', 'vnd-001', 'Microsoft 365', 'SaaS', 'active', 'tier_1', '2026-02-01 10:00:00', 'seed:system'),
('off-002', 'vnd-001', 'Azure', 'Cloud', 'active', 'tier_1', '2026-02-01 10:00:00', 'seed:system'),
('off-004', 'vnd-001', 'Defender For Cloud', 'Security', 'in_review', 'tier_2', '2026-02-01 10:00:00', 'seed:system'),
('off-005', 'vnd-001', 'Power Platform', 'PaaS', 'approved', 'tier_2', '2026-02-01 10:00:00', 'seed:system'),
('off-006', 'vnd-001', 'Dynamics 365 Finance', 'SaaS', 'retired', 'tier_3', '2026-02-01 10:00:00', 'seed:system'),
('off-003', 'vnd-002', 'Sales Cloud', 'SaaS', 'active', 'tier_2', '2026-01-29 09:15:00', 'seed:system');

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

INSERT INTO sec_user_role_map (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at) VALUES
('admin@example.com', 'vendor_admin', 1, 'bootstrap', '2026-01-01 00:00:00', NULL),
('editor@example.com', 'vendor_editor', 1, 'admin@example.com', '2026-01-15 08:00:00', NULL);

INSERT INTO sec_user_org_scope (user_principal, org_id, scope_level, active_flag, granted_at) VALUES
('admin@example.com', 'IT-ENT', 'full', 1, '2026-01-01 00:00:00'),
('editor@example.com', 'SALES-OPS', 'edit', 1, '2026-01-15 08:00:00');

COMMIT;
