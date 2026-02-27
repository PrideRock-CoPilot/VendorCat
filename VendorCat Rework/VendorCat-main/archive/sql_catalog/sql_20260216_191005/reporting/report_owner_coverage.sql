SELECT
  bo.owner_user_principal AS owner_principal,
  bo.owner_role AS owner_role,
  'vendor' AS entity_type,
  bo.vendor_id AS entity_id,
  coalesce(v.display_name, v.legal_name, bo.vendor_id) AS entity_name,
  bo.vendor_id AS vendor_id,
  coalesce(v.display_name, v.legal_name, bo.vendor_id) AS vendor_display_name
FROM {core_vendor_business_owner} bo
LEFT JOIN {core_vendor} v
  ON bo.vendor_id = v.vendor_id
WHERE coalesce(bo.active_flag, true) = true
UNION ALL
SELECT
  obo.owner_user_principal AS owner_principal,
  obo.owner_role AS owner_role,
  'offering' AS entity_type,
  obo.offering_id AS entity_id,
  coalesce(o.offering_name, obo.offering_id) AS entity_name,
  o.vendor_id AS vendor_id,
  coalesce(v2.display_name, v2.legal_name, o.vendor_id) AS vendor_display_name
FROM {core_offering_business_owner} obo
INNER JOIN {core_vendor_offering} o
  ON obo.offering_id = o.offering_id
LEFT JOIN {core_vendor} v2
  ON o.vendor_id = v2.vendor_id
WHERE coalesce(obo.active_flag, true) = true
UNION ALL
SELECT
  p.owner_principal AS owner_principal,
  'project_owner' AS owner_role,
  'project' AS entity_type,
  p.project_id AS entity_id,
  p.project_name AS entity_name,
  p.vendor_id AS vendor_id,
  coalesce(v3.display_name, v3.legal_name, p.vendor_id, 'Unassigned') AS vendor_display_name
FROM {app_project} p
LEFT JOIN {core_vendor} v3
  ON p.vendor_id = v3.vendor_id
WHERE coalesce(p.active_flag, true) = true
  AND p.owner_principal IS NOT NULL
  AND trim(p.owner_principal) <> ''
