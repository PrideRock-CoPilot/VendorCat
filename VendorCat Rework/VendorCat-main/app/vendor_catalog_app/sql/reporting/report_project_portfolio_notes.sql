SELECT project_id, project_note_id
FROM {app_project_note}
WHERE coalesce(active_flag, true) = true
