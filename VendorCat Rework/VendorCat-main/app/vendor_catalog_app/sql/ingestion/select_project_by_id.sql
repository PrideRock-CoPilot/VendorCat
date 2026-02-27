SELECT
  p.project_id,
  p.vendor_id,
  coalesce(v.display_name, v.legal_name, p.vendor_id) AS vendor_display_name,
  p.project_name,
  p.project_type,
  p.status,
  p.start_date,
  p.target_date,
  coalesce(ou.display_name, p.owner_principal) AS owner_principal,
  p.description,
  p.updated_at,
  p.created_at,
  p.created_by,
  p.updated_by
FROM {app_project} p
LEFT JOIN {core_vendor} v
  ON p.vendor_id = v.vendor_id
LEFT JOIN {app_user_directory} ou
  ON lower(p.owner_principal) = lower(ou.user_id)
  OR lower(p.owner_principal) = lower(ou.login_identifier)
WHERE p.project_id = %s
  AND coalesce(p.active_flag, true) = true
LIMIT 1
