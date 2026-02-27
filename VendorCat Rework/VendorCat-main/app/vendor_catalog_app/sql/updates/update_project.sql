UPDATE {app_project}
SET {set_clause},
    updated_at = %s,
    updated_by = %s
WHERE project_id = %s
