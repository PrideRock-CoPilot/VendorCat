SELECT
  project_note_id,
  project_id,
  vendor_id,
  note_text,
  created_at,
  created_by,
  updated_at,
  updated_by
FROM {app_project_note}
WHERE project_id = %s
  {vendor_clause}
  AND coalesce(active_flag, true) = true
ORDER BY created_at DESC
