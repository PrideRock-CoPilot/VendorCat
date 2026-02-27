SELECT project_id, offering_id
FROM {app_project_offering_map}
WHERE coalesce(active_flag, true) = true
