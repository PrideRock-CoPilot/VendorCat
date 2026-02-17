SELECT
  'vendor_owner' AS assignment_type,
  bo.vendor_owner_id AS assignment_id,
  'vendor' AS entity_type,
  bo.vendor_id AS entity_id,
  coalesce(v.display_name, v.legal_name, bo.vendor_id) AS entity_name,
  bo.vendor_id AS vendor_id,
  coalesce(v.display_name, v.legal_name, bo.vendor_id) AS vendor_display_name,
  bo.owner_role AS owner_role,
  bo.owner_user_principal AS owner_user_principal,
  coalesce(u.login_identifier, bo.owner_user_principal) AS owner_principal
FROM {core_vendor_business_owner} bo
LEFT JOIN {core_vendor} v
  ON bo.vendor_id = v.vendor_id
LEFT JOIN {app_user_directory} u
  ON lower(bo.owner_user_principal) = lower(u.user_id)
WHERE coalesce(bo.active_flag, true) = true
UNION ALL
SELECT
  'offering_owner' AS assignment_type,
  obo.offering_owner_id AS assignment_id,
  'offering' AS entity_type,
  obo.offering_id AS entity_id,
  coalesce(o.offering_name, obo.offering_id) AS entity_name,
  o.vendor_id AS vendor_id,
  coalesce(v2.display_name, v2.legal_name, o.vendor_id) AS vendor_display_name,
  obo.owner_role AS owner_role,
  obo.owner_user_principal AS owner_user_principal,
  coalesce(u2.login_identifier, obo.owner_user_principal) AS owner_principal
FROM {core_offering_business_owner} obo
INNER JOIN {core_vendor_offering} o
  ON obo.offering_id = o.offering_id
LEFT JOIN {core_vendor} v2
  ON o.vendor_id = v2.vendor_id
LEFT JOIN {app_user_directory} u2
  ON lower(obo.owner_user_principal) = lower(u2.user_id)
WHERE coalesce(obo.active_flag, true) = true
UNION ALL
SELECT
  'project_owner' AS assignment_type,
  p.project_id AS assignment_id,
  'project' AS entity_type,
  p.project_id AS entity_id,
  coalesce(p.project_name, p.project_id) AS entity_name,
  p.vendor_id AS vendor_id,
  coalesce(v3.display_name, v3.legal_name, p.vendor_id, 'Unassigned') AS vendor_display_name,
  'project_owner' AS owner_role,
  p.owner_principal AS owner_user_principal,
  coalesce(u3.login_identifier, p.owner_principal) AS owner_principal
FROM {app_project} p
LEFT JOIN {core_vendor} v3
  ON p.vendor_id = v3.vendor_id
LEFT JOIN {app_user_directory} u3
  ON lower(p.owner_principal) = lower(u3.user_id)
WHERE coalesce(p.active_flag, true) = true
  AND p.owner_principal IS NOT NULL
  AND trim(p.owner_principal) <> ''
