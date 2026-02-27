INSERT INTO {app_vendor_warning} (
  warning_id,
  vendor_id,
  warning_category,
  severity,
  warning_status,
  warning_title,
  warning_detail,
  source_table,
  source_version,
  file_name,
  detected_at,
  resolved_at,
  created_at,
  created_by,
  updated_at,
  updated_by
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
