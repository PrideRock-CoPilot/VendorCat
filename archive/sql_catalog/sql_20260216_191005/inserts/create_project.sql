INSERT INTO {app_project}
  (project_id, vendor_id, project_name, project_type, status, start_date, target_date, owner_principal, description, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
