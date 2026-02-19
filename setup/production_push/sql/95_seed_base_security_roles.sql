USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

-- Base security seed for production push:
-- - seeds baseline role definitions
-- - seeds role permissions aligned to approval thresholds in app core security policy
-- - does not grant user/group role assignments

DELETE FROM sec_role_definition
WHERE lower(role_code) IN (
  'system_admin',
  'vendor_admin',
  'vendor_approver',
  'vendor_steward',
  'vendor_editor',
  'vendor_viewer',
  'vendor_auditor'
);

INSERT INTO sec_role_definition (
  role_code,
  role_name,
  description,
  approval_level,
  can_edit,
  can_report,
  can_direct_apply,
  active_flag,
  updated_at,
  updated_by
)
VALUES
  ('system_admin',    'System Admin',    'Platform administration access. Cannot edit vendor data or approve business changes.', 0,  false, true,  false, true, current_timestamp(), 'seed:system'),
  ('vendor_admin',    'Vendor Admin',    'Full administrative access across all workflows and data changes.',                     10, true,  true,  true,  true, current_timestamp(), 'seed:system'),
  ('vendor_approver', 'Vendor Approver', 'Can review and approve requests but cannot directly edit vendor records.',              7,  false, true,  false, true, current_timestamp(), 'seed:system'),
  ('vendor_steward',  'Vendor Steward',  'Data steward with elevated review/apply rights for governed updates.',                  7,  true,  true,  true,  true, current_timestamp(), 'seed:system'),
  ('vendor_editor',   'Vendor Editor',   'Contributor role for day-to-day edits and change submissions.',                        4,  true,  true,  false, true, current_timestamp(), 'seed:system'),
  ('vendor_viewer',   'Vendor Viewer',   'Read-only access to vendor inventory and metadata.',                                   0,  false, false, false, true, current_timestamp(), 'seed:system'),
  ('vendor_auditor',  'Vendor Auditor',  'Read/report access for governance and audit functions.',                               0,  false, true,  false, true, current_timestamp(), 'seed:system');

DELETE FROM sec_role_permission
WHERE lower(object_name) = 'change_action'
  AND lower(role_code) IN (
    'system_admin',
    'vendor_admin',
    'vendor_approver',
    'vendor_steward',
    'vendor_editor',
    'vendor_viewer',
    'vendor_auditor'
  );

INSERT INTO sec_role_permission (
  role_code,
  object_name,
  action_code,
  active_flag,
  updated_at
)
WITH role_seed AS (
  SELECT role_code, CAST(approval_level AS INT) AS approval_level
  FROM sec_role_definition
  WHERE lower(role_code) IN (
    'system_admin',
    'vendor_admin',
    'vendor_approver',
    'vendor_steward',
    'vendor_editor',
    'vendor_viewer',
    'vendor_auditor'
  )
),
action_seed AS (
  SELECT 'feedback_submit' AS action_code, 0 AS required_level
  UNION ALL SELECT 'report_submit', 0
  UNION ALL SELECT 'request_access', 3
  UNION ALL SELECT 'create_vendor_profile', 9
  UNION ALL SELECT 'update_vendor_profile', 6
  UNION ALL SELECT 'update_offering', 6
  UNION ALL SELECT 'create_offering', 6
  UNION ALL SELECT 'create_contract', 6
  UNION ALL SELECT 'update_contract', 6
  UNION ALL SELECT 'map_contract_to_offering', 6
  UNION ALL SELECT 'map_demo_to_offering', 3
  UNION ALL SELECT 'add_vendor_owner', 6
  UNION ALL SELECT 'add_vendor_org_assignment', 6
  UNION ALL SELECT 'add_vendor_contact', 3
  UNION ALL SELECT 'add_offering_owner', 6
  UNION ALL SELECT 'remove_offering_owner', 6
  UNION ALL SELECT 'add_offering_contact', 3
  UNION ALL SELECT 'remove_offering_contact', 3
  UNION ALL SELECT 'update_offering_profile', 6
  UNION ALL SELECT 'add_offering_note', 3
  UNION ALL SELECT 'add_offering_ticket', 3
  UNION ALL SELECT 'update_offering_ticket', 3
  UNION ALL SELECT 'add_offering_invoice', 3
  UNION ALL SELECT 'remove_offering_invoice', 3
  UNION ALL SELECT 'create_project', 6
  UNION ALL SELECT 'update_project', 6
  UNION ALL SELECT 'update_project_owner', 6
  UNION ALL SELECT 'attach_project_vendor', 6
  UNION ALL SELECT 'attach_project_offering', 6
  UNION ALL SELECT 'add_project_note', 3
  UNION ALL SELECT 'create_project_demo', 6
  UNION ALL SELECT 'update_project_demo', 3
  UNION ALL SELECT 'remove_project_demo', 3
  UNION ALL SELECT 'create_doc_link', 3
  UNION ALL SELECT 'remove_doc_link', 3
  UNION ALL SELECT 'create_demo_outcome', 6
  UNION ALL SELECT 'record_contract_cancellation', 9
  UNION ALL SELECT 'grant_role', 9
  UNION ALL SELECT 'grant_scope', 9
)
SELECT
  r.role_code,
  'change_action' AS object_name,
  action_seed.action_code,
  true AS active_flag,
  current_timestamp() AS updated_at
FROM role_seed r
INNER JOIN action_seed
  ON r.approval_level >= action_seed.required_level;
