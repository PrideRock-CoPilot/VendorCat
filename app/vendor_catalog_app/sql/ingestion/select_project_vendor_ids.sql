SELECT DISTINCT vendor_id
FROM {app_project_vendor_map}
WHERE project_id = %s
  AND coalesce(active_flag, true) = true
