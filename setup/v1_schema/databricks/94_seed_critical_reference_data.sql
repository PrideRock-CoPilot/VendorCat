USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

-- Critical POC seed only:
-- - lookup/dropdown options required for core forms and admin defaults
-- - excludes full synthetic test dataset

DELETE FROM app_lookup_option
WHERE lookup_type IN (
  'doc_source',
  'doc_tag',
  'owner_role',
  'assignment_type',
  'contact_type',
  'project_type',
  'offering_type',
  'offering_lob',
  'offering_service_type',
  'workflow_status'
);

INSERT INTO app_lookup_option
  (option_id, lookup_type, option_code, option_label, sort_order, active_flag, valid_from_ts, valid_to_ts, is_current, deleted_flag, updated_at, updated_by)
VALUES
  ('lk-docsrc-001', 'doc_source', 'sharepoint', 'sharepoint', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-002', 'doc_source', 'onedrive', 'onedrive', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-003', 'doc_source', 'confluence', 'confluence', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-004', 'doc_source', 'google_drive', 'google_drive', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-005', 'doc_source', 'box', 'box', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-006', 'doc_source', 'dropbox', 'dropbox', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-007', 'doc_source', 'github', 'github', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-docsrc-008', 'doc_source', 'other', 'other', 80, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-doctag-001', 'doc_tag', 'contract', 'contract', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-002', 'doc_tag', 'msa', 'msa', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-003', 'doc_tag', 'nda', 'nda', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-004', 'doc_tag', 'sow', 'sow', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-005', 'doc_tag', 'invoice', 'invoice', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-006', 'doc_tag', 'renewal', 'renewal', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-007', 'doc_tag', 'security', 'security', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-008', 'doc_tag', 'architecture', 'architecture', 80, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-009', 'doc_tag', 'runbook', 'runbook', 90, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-010', 'doc_tag', 'compliance', 'compliance', 100, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-011', 'doc_tag', 'rfp', 'rfp', 110, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-012', 'doc_tag', 'poc', 'poc', 120, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-013', 'doc_tag', 'notes', 'notes', 130, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-014', 'doc_tag', 'operations', 'operations', 140, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-doctag-015', 'doc_tag', 'folder', 'folder', 150, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-ownrole-001', 'owner_role', 'business_owner', 'business_owner', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-002', 'owner_role', 'executive_owner', 'executive_owner', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-003', 'owner_role', 'service_owner', 'service_owner', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-004', 'owner_role', 'technical_owner', 'technical_owner', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-005', 'owner_role', 'security_owner', 'security_owner', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-006', 'owner_role', 'application_owner', 'application_owner', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-007', 'owner_role', 'platform_owner', 'platform_owner', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-ownrole-008', 'owner_role', 'legacy_owner', 'legacy_owner', 80, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-asgntype-001', 'assignment_type', 'consumer', 'consumer', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-asgntype-002', 'assignment_type', 'primary', 'primary', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-asgntype-003', 'assignment_type', 'secondary', 'secondary', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-contact-001', 'contact_type', 'business', 'business', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-contact-002', 'contact_type', 'account_manager', 'account_manager', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-contact-003', 'contact_type', 'support', 'support', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-contact-004', 'contact_type', 'escalation', 'escalation', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-contact-005', 'contact_type', 'security_specialist', 'security_specialist', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-contact-006', 'contact_type', 'customer_success', 'customer_success', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-contact-007', 'contact_type', 'product_manager', 'product_manager', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-prjtype-001', 'project_type', 'rfp', 'rfp', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-prjtype-002', 'project_type', 'poc', 'poc', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-prjtype-003', 'project_type', 'renewal', 'renewal', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-prjtype-004', 'project_type', 'implementation', 'implementation', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-prjtype-005', 'project_type', 'other', 'other', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-offtype-001', 'offering_type', 'saas', 'SaaS', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offtype-002', 'offering_type', 'cloud', 'Cloud', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offtype-003', 'offering_type', 'paas', 'PaaS', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offtype-004', 'offering_type', 'security', 'Security', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offtype-005', 'offering_type', 'data', 'Data', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offtype-006', 'offering_type', 'integration', 'Integration', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offtype-007', 'offering_type', 'other', 'Other', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-offlob-001', 'offering_lob', 'enterprise', 'Enterprise', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offlob-002', 'offering_lob', 'finance', 'Finance', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offlob-003', 'offering_lob', 'hr', 'HR', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offlob-004', 'offering_lob', 'it', 'IT', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offlob-005', 'offering_lob', 'operations', 'Operations', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offlob-006', 'offering_lob', 'sales', 'Sales', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offlob-007', 'offering_lob', 'security', 'Security', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-offsvc-001', 'offering_service_type', 'application', 'Application', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-002', 'offering_service_type', 'infrastructure', 'Infrastructure', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-003', 'offering_service_type', 'integration', 'Integration', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-004', 'offering_service_type', 'managed_service', 'Managed Service', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-005', 'offering_service_type', 'platform', 'Platform', 50, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-006', 'offering_service_type', 'security', 'Security', 60, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-007', 'offering_service_type', 'support', 'Support', 70, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-offsvc-008', 'offering_service_type', 'other', 'Other', 80, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),

  ('lk-wf-001', 'workflow_status', 'submitted', 'submitted', 10, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-wf-002', 'workflow_status', 'in_review', 'in_review', 20, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-wf-003', 'workflow_status', 'approved', 'approved', 30, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system'),
  ('lk-wf-004', 'workflow_status', 'rejected', 'rejected', 40, 1, '2026-01-01 00:00:00', null, 1, 0, current_timestamp(), 'seed:system');
