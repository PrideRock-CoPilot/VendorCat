SELECT
  p.project_id,
  p.vendor_id,
  p.project_name,
  p.project_type,
  p.status,
  p.start_date,
  p.target_date,
  coalesce(ou.display_name, p.owner_principal) AS owner_principal,
  p.description,
  p.updated_at,
  COALESCE(d.demo_count, 0) AS demo_count,
  CASE
    WHEN d.last_demo_at IS NOT NULL AND d.last_demo_at > p.updated_at THEN d.last_demo_at
    ELSE p.updated_at
  END AS last_activity_at
FROM {app_project} p
LEFT JOIN {app_user_directory} ou
  ON lower(p.owner_principal) = lower(ou.user_id)
  OR lower(p.owner_principal) = lower(ou.login_identifier)
LEFT JOIN (
  SELECT project_id, COUNT(*) AS demo_count, MAX(updated_at) AS last_demo_at
  FROM {app_project_demo}
  WHERE coalesce(active_flag, true) = true
  GROUP BY project_id
) d
  ON p.project_id = d.project_id
WHERE (
  p.project_id IN (
    SELECT project_id
    FROM {app_project_vendor_map}
    WHERE vendor_id = %s
      AND coalesce(active_flag, true) = true
  )
  OR p.vendor_id = %s
)
  AND coalesce(p.active_flag, true) = true
ORDER BY p.status, p.project_name
