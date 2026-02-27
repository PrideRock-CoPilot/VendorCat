UPDATE {app_project_demo}
SET active_flag = false,
    updated_at = %s,
    updated_by = %s
WHERE project_demo_id = %s
  AND project_id = %s
  AND vendor_id = %s
