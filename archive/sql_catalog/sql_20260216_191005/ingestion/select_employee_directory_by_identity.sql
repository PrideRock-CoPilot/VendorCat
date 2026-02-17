SELECT
  login_identifier,
  email,
  network_id,
  employee_id,
  manager_id,
  first_name,
  last_name,
  display_name,
  active_flag
FROM {employee_directory_view}
WHERE coalesce(active_flag, true) = true
  AND (
    lower(coalesce(login_identifier, '')) = lower(%s)
    OR lower(coalesce(email, '')) = lower(%s)
    OR lower(coalesce(network_id, '')) = lower(%s)
    OR lower(coalesce(employee_id, '')) = lower(%s)
  )
LIMIT 1
