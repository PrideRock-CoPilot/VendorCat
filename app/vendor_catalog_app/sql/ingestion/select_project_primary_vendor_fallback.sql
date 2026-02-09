SELECT vendor_id
FROM {app_project}
WHERE project_id = %s
  AND coalesce(active_flag, true) = true
LIMIT 1
