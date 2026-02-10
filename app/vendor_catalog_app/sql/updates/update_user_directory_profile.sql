UPDATE {app_user_directory}
SET
  email = %s,
  network_id = %s,
  first_name = %s,
  last_name = %s,
  display_name = %s,
  updated_at = %s,
  last_seen_at = %s
WHERE user_id = %s
