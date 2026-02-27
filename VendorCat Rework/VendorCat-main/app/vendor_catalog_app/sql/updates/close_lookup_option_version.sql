UPDATE {app_lookup_option}
SET
  valid_to_ts = %s,
  is_current = %s,
  updated_at = %s,
  updated_by = %s
WHERE option_id = %s
