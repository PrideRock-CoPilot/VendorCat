SELECT project_id, vendor_id
FROM {app_project_vendor_map}
WHERE coalesce(active_flag, true) = true
UNION ALL
SELECT project_id, vendor_id
FROM {app_project}
WHERE vendor_id IS NOT NULL
  AND coalesce(active_flag, true) = true
