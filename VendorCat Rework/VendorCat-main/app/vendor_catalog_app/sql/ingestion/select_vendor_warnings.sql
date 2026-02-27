SELECT
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
FROM {app_vendor_warning}
WHERE vendor_id = %s
  AND ({status_filter_disabled} OR lower(coalesce(warning_status, '')) = lower(%s))
ORDER BY
  CASE lower(coalesce(warning_status, 'open'))
    WHEN 'open' THEN 0
    WHEN 'monitoring' THEN 1
    WHEN 'dismissed' THEN 2
    WHEN 'resolved' THEN 3
    ELSE 9
  END,
  coalesce(detected_at, created_at, updated_at) DESC,
  updated_at DESC
