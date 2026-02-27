SELECT
  user_id,
  login_identifier,
  email,
  network_id,
  employee_id,
  manager_id,
  first_name,
  last_name,
  display_name,
  active_flag,
  last_seen_at
FROM {app_user_directory}
WHERE lower(login_identifier) = lower(%s)
LIMIT 1
