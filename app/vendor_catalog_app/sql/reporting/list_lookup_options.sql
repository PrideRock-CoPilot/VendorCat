SELECT
  option_id,
  lookup_type,
  option_code,
  option_label,
  sort_order,
  active_flag,
  valid_from_ts,
  valid_to_ts,
  is_current,
  deleted_flag,
  updated_at,
  updated_by
FROM {app_lookup_option}
WHERE (%s IS NULL OR lookup_type = %s)
ORDER BY lookup_type, sort_order, option_code
