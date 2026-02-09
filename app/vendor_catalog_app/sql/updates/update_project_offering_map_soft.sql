UPDATE {app_project_offering_map}
SET active_flag = false,
    updated_at = %s,
    updated_by = %s
WHERE project_id = %s
