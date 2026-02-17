INSERT INTO {app_project_note}
  (project_note_id, project_id, vendor_id, note_text, active_flag, created_at, created_by, updated_at, updated_by)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
