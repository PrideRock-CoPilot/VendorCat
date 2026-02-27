UPDATE {app_project}
SET owner_principal = %s,
    updated_at = %s,
    updated_by = %s
WHERE project_id = %s
  AND coalesce(active_flag, true) = true
